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
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_ecr_assets as ecr_assets,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
    aws_route53 as r53,
    aws_route53_targets as r53_targets,
    aws_cloudwatch as cloudwatch,
    aws_logs as logs,
)


class PolicyAtlasStack(Stack):
    def __init__(self, scope: Stack, id: str, pa_config: dict, env_name: str, **kwargs) -> None:
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

        be_task_def = ecs.FargateTaskDefinition(self, "PolicyAtlasBackendTaskDef",
            cpu=be_config["cpu"],
            memory_limit_mib=be_config["memory_limit_mib"],
            family="policy-atlas-v3-api",
        )

        be_task_def.add_container("policy-atlas-backend-container",
            image=ecs.ContainerImage.from_asset("../backend",
                platform=ecr_assets.Platform.LINUX_AMD64,
            ),
            cpu=be_config["cpu"],
            memory_limit_mib=be_config["memory_limit_mib"],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="PolicyAtlasBackend",
                                            log_group=shared_log_group),
            environment={
                "LOG_LEVEL": "INFO",
            },
            secrets={
                # B.3 completes the full application env/secret map.
                "DATABASE_URL": ecs.Secret.from_secrets_manager(db_secret, field="db_connection_string"),
            },
            port_mappings=[ecs.PortMapping(
                container_port=be_config["internal_port"],
                protocol=ecs.Protocol.TCP
            )],
            stop_timeout=Duration.seconds(10),
        )

        db_secret.grant_read(be_task_def.task_role)

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

        # Phase B (B.3): /policy_atlas_v3/deploy/migration_task_def_arn is
        # exported here once the one-shot ECS Alembic migration task definition
        # is added to this stack.
