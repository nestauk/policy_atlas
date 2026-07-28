# Application stack. Deploys the following resources:
# * Policy Atlas backend (FastAPI) as an ECS Fargate service
# * Route53 A record for the API (pointing to the shared ALB in NetworkStack)
# * Security groups: backend containers
# * DB security group ingress rule so backend can reach RDS (port 5432)
# * Listener rule on the shared ALB for host-header routing
#
# Pre-requisites (deployed separately):
# * NetworkStack (provides shared ALB, HTTPS listener, security group via SSM)
# * DatabaseStack (provides /policy_atlas_v3/db/secret_name and
#   /policy_atlas_v3/db/security_group_id in SSM)
#
# Frontend (Next.js, served from S3/CloudFront) and its DNS are added in Phase B
# alongside PaV3CertStack — this stack no longer builds or serves the frontend.
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr_assets as ecr_assets,
    aws_elasticloadbalancingv2 as elbv2,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
    aws_route53 as r53,
    aws_route53_targets as r53_targets,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as cloudfront_origins,
    aws_certificatemanager as acm,
    aws_logs as logs,
)
from infra.cognito_auth import CognitoAuth


class PolicyAtlasStack(Stack):
    def __init__(self, scope: Stack, id: str, pa_config: dict,
                 certificate: acm.ICertificate, env_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        pa_app_config = pa_config["policy_atlas_config"]
        domain_name = pa_app_config["domain_name"]
        be_config = pa_app_config["backend"]

        be_domain = f"{pa_app_config['backend_subdomain']}.{domain_name}"

        vpc = ec2.Vpc.from_lookup(self, "VPC", region=pa_config['aws_region'],
            vpc_name="policy-atlas-v3-vpc-" + env_name)

        hosted_zone = r53.HostedZone.from_lookup(self, "HostedZone",
            domain_name=domain_name
        )

        # --- Import shared ALB from NetworkStack ---
        shared_alb_arn = ssm.StringParameter.value_for_string_parameter(self,
            parameter_name="/policy_atlas_v3/shared_alb/arn")
        shared_alb_sg_id = ssm.StringParameter.value_for_string_parameter(self,
            parameter_name="/policy_atlas_v3/shared_alb/security_group_id")
        shared_alb_dns = ssm.StringParameter.value_for_string_parameter(self,
            parameter_name="/policy_atlas_v3/shared_alb/dns_name")
        shared_alb_zone_id = ssm.StringParameter.value_for_string_parameter(self,
            parameter_name="/policy_atlas_v3/shared_alb/canonical_hosted_zone_id")
        shared_listener_arn = ssm.StringParameter.value_for_string_parameter(self,
            parameter_name="/policy_atlas_v3/shared_alb/https_listener_arn")

        shared_alb_sg = ec2.SecurityGroup.from_security_group_id(
            self, "SharedALBSG", security_group_id=shared_alb_sg_id,
            allow_all_outbound=False,
        )

        shared_alb = elbv2.ApplicationLoadBalancer.from_application_load_balancer_attributes(
            self, "SharedALB",
            load_balancer_arn=shared_alb_arn,
            security_group_id=shared_alb_sg_id,
            load_balancer_dns_name=shared_alb_dns,
            load_balancer_canonical_hosted_zone_id=shared_alb_zone_id,
        )

        shared_listener = elbv2.ApplicationListener.from_application_listener_attributes(
            self, "SharedHTTPSListener",
            listener_arn=shared_listener_arn,
            security_group=shared_alb_sg,
        )

        # --- Import DB resources from DatabaseStack ---
        db_secret_name = ssm.StringParameter.value_for_string_parameter(self,
            parameter_name="/policy_atlas_v3/db/secret_name"
        )

        db_secret = secretsmanager.Secret.from_secret_name_v2(self, "DBSecret",
            secret_name=db_secret_name
        )

        db_sg_id = ssm.StringParameter.value_for_string_parameter(self,
            parameter_name="/policy_atlas_v3/db/security_group_id"
        )

        db_security_group = ec2.SecurityGroup.from_security_group_id(
            self, "DBSecurityGroup", security_group_id=db_sg_id,
            allow_all_outbound=False
        )

        app_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "AppSecret", secret_name=be_config["secret_name"]
        )

        shared_log_group = logs.LogGroup(self, "PolicyAtlasLogGroup",
            log_group_name="/policy_atlas_v3/application",
            retention=logs.RetentionDays.ONE_MONTH,
        )

        cluster = ecs.Cluster(self, "PolicyAtlasCluster", vpc=vpc,
            cluster_name="policy-atlas-v3-cluster"
        )

        # --- Security groups ---
        # Backend containers allow inbound only from the shared ALB.

        be_sg = ec2.SecurityGroup(self, "BackendSG",
            vpc=vpc,
            description="Policy Atlas backend containers",
            allow_all_outbound=True
        )
        be_sg.add_ingress_rule(shared_alb_sg, ec2.Port.tcp(be_config["internal_port"]),
            "Allow shared ALB to reach FastAPI containers"
        )

        # Allow backend containers to connect to RDS on port 5432.
        db_security_group.add_ingress_rule(be_sg, ec2.Port.tcp(5432),
            "Allow Policy Atlas backend containers to connect to RDS"
        )

        # --- Backend ---

        auth = CognitoAuth(self, "CognitoAuth")
        backend_image = ecs.ContainerImage.from_asset("../backend",
            platform=ecr_assets.Platform.LINUX_AMD64,
        )

        be_task_def = ecs.FargateTaskDefinition(self, "PolicyAtlasBackendTaskDef",
            cpu=be_config["cpu"],
            memory_limit_mib=be_config["memory_limit_mib"],
            family="policy-atlas-v3-api",
        )

        be_task_def.add_container("policy-atlas-backend-container",
            image=backend_image,
            cpu=be_config["cpu"],
            memory_limit_mib=be_config["memory_limit_mib"],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="PolicyAtlasBackend",
                                            log_group=shared_log_group),
            environment={
                "OIDC_ISSUER": auth.issuer,
                "OIDC_JWKS_URL": auth.jwks_url,
                "OIDC_CLIENT_ID": auth.client_id_value,
                "APP_ORIGIN": f"https://{domain_name}",
                "PA_BACKEND_MODE": "live",
                "RUN_EXECUTOR_MAX": str(be_config["run_executor_max"]),
                "DB_POOL_SIZE": str(be_config["db_pool_size"]),
                "DB_MAX_OVERFLOW": str(be_config["db_max_overflow"]),
                "LOG_LEVEL": "INFO",
            },
            secrets={
                "DATABASE_URL": ecs.Secret.from_secrets_manager(db_secret, field="db_connection_string"),
                "OPENAI_API_KEY": ecs.Secret.from_secrets_manager(app_secret, field="OPENAI_API_KEY"),
                "OPENALEX_EMAIL": ecs.Secret.from_secrets_manager(app_secret, field="OPENALEX_EMAIL"),
                "OPENALEX_API_KEY": ecs.Secret.from_secrets_manager(app_secret, field="OPENALEX_API_KEY"),
                "OVERTON_API_KEY": ecs.Secret.from_secrets_manager(app_secret, field="OVERTON_API_KEY"),
                "LANGFUSE_PUBLIC_KEY": ecs.Secret.from_secrets_manager(app_secret, field="LANGFUSE_PUBLIC_KEY"),
                "LANGFUSE_SECRET_KEY": ecs.Secret.from_secrets_manager(app_secret, field="LANGFUSE_SECRET_KEY"),
                # LANGFUSE_HOST, not LANGFUSE_BASE_URL: tracing.py accepts both;
                # the provisioned secret carries v2's key name (E.1 deviation,
                # verification.md) — adapting here beats patching a live secret.
                "LANGFUSE_HOST": ecs.Secret.from_secrets_manager(app_secret, field="LANGFUSE_HOST"),
            },
            port_mappings=[ecs.PortMapping(
                container_port=be_config["internal_port"],
                protocol=ecs.Protocol.TCP
            )],
            stop_timeout=Duration.seconds(10),
        )

        # No task-role secret grants: ECS injects container secrets through the
        # EXECUTION role (CDK grants it via ecs.Secret.from_secrets_manager);
        # the app never calls Secrets Manager at runtime, so a task-role grant
        # would only widen what a compromised process could read.

        migration_task_def = ecs.FargateTaskDefinition(
            self, "PolicyAtlasMigrationTaskDef",
            cpu=512,
            memory_limit_mib=1024,
            family="policy-atlas-v3-migrate",
        )
        migration_task_def.add_container("policy-atlas-migration-container",
            image=backend_image,
            command=["alembic", "upgrade", "head"],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="Migrate",
                                            log_group=shared_log_group),
            secrets={
                "DATABASE_URL": ecs.Secret.from_secrets_manager(
                    db_secret, field="db_connection_string"
                ),
            },
        )

        be_service = ecs.FargateService(self, "PolicyAtlasBackendService",
            cluster=cluster,
            task_definition=be_task_def,
            # Template-pinned invariant: this stack never scales the service up.
            # Deploys (B.3+) flip desired_count via a separate deploy step, not CDK.
            desired_count=0,
            min_healthy_percent=0,
            max_healthy_percent=100,
            service_name="policy-atlas-v3-api-service",
            security_groups=[be_sg],
            assign_public_ip=False,
        )

        # Backend listener rule + DNS
        backend_tg = elbv2.ApplicationTargetGroup(self, "BackendTargetGroup",
            vpc=vpc,
            target_group_name="pa-v3-api-tg",
            port=be_config["internal_port"],
            protocol=elbv2.ApplicationProtocol.HTTP,
            health_check=elbv2.HealthCheck(
                path="/readyz",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=5,
                healthy_http_codes="200-399",
            ),
            targets=[be_service.load_balancer_target(
                container_name="policy-atlas-backend-container",
                container_port=be_config["internal_port"],
                protocol=ecs.Protocol.TCP
            )]
        )

        shared_listener.add_target_groups("BackendListenerRule",
            priority=10,
            conditions=[elbv2.ListenerCondition.host_headers([be_domain])],
            target_groups=[backend_tg]
        )

        r53.ARecord(self, "BackendARecord",
            zone=hosted_zone,
            record_name=pa_app_config["backend_subdomain"],
            target=r53.RecordTarget.from_alias(r53_targets.LoadBalancerTarget(shared_alb))
        )

        # Frontend DNS (apex A record) moves to CloudFront in Phase B — no
        # frontend ARecord here.

        # --- Cognito auth and static SPA delivery ---

        frontend_bucket = s3.Bucket(self, "FrontendBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )
        fonts_bucket = s3.Bucket(self, "FontsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
        )

        index_html_cache_policy = cloudfront.CachePolicy(self, "IndexHtmlCachePolicy",
            default_ttl=Duration.seconds(60),
            min_ttl=Duration.seconds(0),
            max_ttl=Duration.seconds(60),
        )
        frontend_origin = cloudfront_origins.S3BucketOrigin.with_origin_access_control(
            frontend_bucket,
        )
        # Review-stack hardening (026 step 7): baseline security headers (HSTS,
        # X-Frame-Options, nosniff, referrer policy) on every response.
        security_headers = cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS
        distribution = cloudfront.Distribution(self, "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=frontend_origin,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=security_headers,
            ),
            additional_behaviors={
                "/index.html": cloudfront.BehaviorOptions(
                    origin=frontend_origin,
                    cache_policy=index_html_cache_policy,
                    response_headers_policy=security_headers,
                ),
            },
            certificate=certificate,
            domain_names=[domain_name],
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        r53.ARecord(self, "FrontendARecord",
            zone=hosted_zone,
            target=r53.RecordTarget.from_alias(r53_targets.CloudFrontTarget(distribution)),
        )
        r53.AaaaRecord(self, "FrontendAaaaRecord",
            zone=hosted_zone,
            target=r53.RecordTarget.from_alias(r53_targets.CloudFrontTarget(distribution)),
        )

        # --- Deploy SSM exports (consumed by scripts/deploy.sh, D.1) ---
        ssm.StringParameter(self, "PrivateSubnetIdsParameter",
            parameter_name="/policy_atlas_v3/deploy/private_subnet_ids",
            string_value=",".join(vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnet_ids)
        )

        ssm.StringParameter(self, "ClusterArnParameter",
            parameter_name="/policy_atlas_v3/deploy/cluster_arn",
            string_value=cluster.cluster_arn
        )

        ssm.StringParameter(self, "MigrationTaskDefArnParameter",
            parameter_name="/policy_atlas_v3/deploy/migration_task_def_arn",
            string_value=migration_task_def.task_definition_arn,
        )

        ssm.StringParameter(self, "FrontendBucketNameParameter",
            parameter_name="/policy_atlas_v3/deploy/frontend_bucket_name",
            string_value=frontend_bucket.bucket_name,
        )

        ssm.StringParameter(self, "FontsBucketNameParameter",
            parameter_name="/policy_atlas_v3/deploy/fonts_bucket_name",
            string_value=fonts_bucket.bucket_name,
        )

        ssm.StringParameter(self, "DistributionIdParameter",
            parameter_name="/policy_atlas_v3/deploy/distribution_id",
            string_value=distribution.distribution_id,
        )
