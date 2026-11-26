# Application stack. Deploys the following resources:
# * Policy Atlas backend (FastAPI) as an ECS Fargate service
# * Route53 A record for the API (pointing to the shared ALB in NetworkStack)
# * Security groups: backend containers
# * DB security group ingress rule so backend can reach RDS (port 5432)
# * Listener rule on the shared ALB for host-header routing
# * The queued document-ingest worker: queue, dead-letter queue,
#   Lambda function and its dead-letter alarm (components/ingest_worker.py)
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
    aws_iam as iam,
)
from aws_cdk import Fn
from infra.cognito_auth import CognitoAuth, sign_in_block
from infra.components.ingest_worker import IngestWorker
from infra.components.shared_alb import import_shared_alb
from infra.components.security_headers import SecurityHeaders, content_security_policy
from infra.components.waf import ApiFirewall

# How the API reads documents' full text: "in_process" parses them
# inside the API task as before; "queued" sends one message per document to
# the ingest function. Set per environment in pa_config.json.
INGEST_MODES = ("in_process", "queued")


class PolicyAtlasStack(Stack):
    def __init__(self, scope: Stack, id: str, pa_config: dict,
                 certificate: acm.ICertificate, env_name: str,
                 ops_allowlist_size: int = 1,
                 auth_certificate: acm.ICertificate | None = None,
                 metabase_host: str | None = None,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        pa_app_config = pa_config["policy_atlas_config"]
        domain_name = pa_app_config["domain_name"]
        be_config = pa_app_config["backend"]
        ops_config = pa_app_config["ops"]
        self_signup_config = pa_app_config["self_signup"]
        sign_in_config = sign_in_block(pa_app_config.get("sign_in"))
        auth_domain = sign_in_config.get("domain")

        if type(ops_allowlist_size) is not int or not 1 <= ops_allowlist_size <= 8:
            raise ValueError("ops_allowlist_size must be an integer from 1 to 8")

        be_domain = f"{pa_app_config['backend_subdomain']}.{domain_name}"
        ops_domain = f"{ops_config['subdomain']}.{domain_name}"

        vpc = ec2.Vpc.from_lookup(self, "VPC", region=pa_config['aws_region'],
            vpc_name="policy-atlas-v3-vpc-" + env_name)

        hosted_zone = r53.HostedZone.from_lookup(self, "HostedZone",
            domain_name=domain_name
        )

        # --- Import shared ALB from NetworkStack (SSM-resolved at deploy time) ---
        shared_alb_imports = import_shared_alb(self)
        shared_alb_sg = shared_alb_imports.security_group
        shared_alb = shared_alb_imports.load_balancer
        shared_listener = shared_alb_imports.listener

        # The firewall in front of the API, the ops pages and Metabase
        # (ADR 0047). Reads backend.waf from pa_config.json; nothing from it
        # reaches the container. metabase_host is None where the analytics
        # stack is not deployed.
        ApiFirewall(self, "ApiFirewall",
            load_balancer_arn=shared_alb.load_balancer_arn,
            hosts=[be_domain, ops_domain, *([metabase_host] if metabase_host else [])],
            domain_name=domain_name,
            waf_config=be_config.get("waf"),
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

        # Which AI models the backend uses: a route name from the backend's
        # committed file backend/src/policy_atlas/model_routes.toml.
        # "openai-direct" calls OpenAI with OPENAI_API_KEY; a "bedrock-*" route
        # calls Amazon Bedrock with AWS_BEARER_TOKEN_BEDROCK. The Bedrock key is
        # only passed when a Bedrock route is chosen, because ECS refuses to start
        # a task whose secret names a field the secret does not have: add the
        # field to the app secret first, then switch the route in pa_config.json.
        model_route = be_config.get("model_route", "openai-direct")
        ingest_mode = be_config.get("ingest_mode")
        # The API creates theory-of-change tasks only where this
        # is "1". On in staging for colleagues to try; off in production until
        # the capability is complete.
        theory_of_change = "1" if be_config.get("theory_of_change") else "0"
        if ingest_mode not in INGEST_MODES:
            raise ValueError(
                f"backend.ingest_mode must be one of {INGEST_MODES} in pa_config.json, "
                f"got {ingest_mode!r}."
            )
        app_secrets = {
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
        }
        if model_route.startswith("bedrock"):
            app_secrets["AWS_BEARER_TOKEN_BEDROCK"] = ecs.Secret.from_secrets_manager(
                app_secret, field="AWS_BEARER_TOKEN_BEDROCK"
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

        auth = CognitoAuth(
            self,
            "CognitoAuth",
            domain_name=domain_name,
            domain_prefix=pa_app_config["cognito_domain_prefix"],
            email=pa_app_config.get("email"),
            extra_domains=[ops_domain],
            sign_in=sign_in_config,
            auth_certificate=auth_certificate,
            hosted_zone=hosted_zone,
        )
        # One image build for three consumers: the API task, the migration
        # task and the ingest function (which starts it with another command).
        backend_image_asset = ecr_assets.DockerImageAsset(self, "BackendImageAsset",
            directory="../backend",
            platform=ecr_assets.Platform.LINUX_AMD64,
        )
        backend_image = ecs.ContainerImage.from_docker_image_asset(backend_image_asset)

        ingest = IngestWorker(self, "Ingest",
            vpc=vpc,
            image_asset=backend_image_asset,
            db_secret=db_secret,
            db_security_group=db_security_group,
            model_route=model_route,
        )

        # Files users give a task (one bucket for every capability). Private,
        # encrypted, HTTPS only, and kept if the stack is ever deleted: they are
        # users' work. Only the backend
        # reads it; the browser never does.
        uploads_bucket = s3.Bucket(self, "UploadsBucket",
            bucket_name=be_config["upload_bucket_name"],
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=False,
            removal_policy=RemovalPolicy.RETAIN,
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
                "RUNS_PER_USER": str(be_config["runs_per_user"]),
                "TASK_QUOTA_PER_YEAR": str(be_config["task_quota_per_year"]),
                # Uvicorn (the web server) takes the client address from the
                # leftmost X-Forwarded-For entry when the request comes from a
                # trusted proxy. "*" would trust anyone, letting a client write
                # that entry; the VPC (private network) range trusts only the
                # load balancer.
                "FORWARDED_ALLOW_IPS": vpc.vpc_cidr_block,
                "DB_POOL_SIZE": str(be_config["db_pool_size"]),
                "DB_MAX_OVERFLOW": str(be_config["db_max_overflow"]),
                "LOG_LEVEL": "INFO",
                "LOG_FORMAT": "json",
                # Tags deployed traces so they filter apart from local-dev
                # runs inside the shared dev Langfuse project.
                "LANGFUSE_TRACING_ENVIRONMENT": env_name,
                "POLICY_ATLAS_MODEL_ROUTE": model_route,
                "POLICY_ATLAS_UPLOAD_BUCKET": uploads_bucket.bucket_name,
                "POLICY_ATLAS_THEORY_OF_CHANGE": theory_of_change,
                "POLICY_ATLAS_INGEST_MODE": ingest_mode,
                "POLICY_ATLAS_INGEST_QUEUE_URL": ingest.queue.queue_url,
            },
            secrets=app_secrets,
            port_mappings=[ecs.PortMapping(
                container_port=be_config["internal_port"],
                protocol=ecs.Protocol.TCP
            )],
            stop_timeout=Duration.seconds(10),
        )

        # The backend reads, writes and deletes uploads under tasks/ only, through
        # its task role: AWS hands the container short-lived credentials, so no
        # keys are stored anywhere.
        uploads_bucket.grant_read_write(be_task_def.task_role, "tasks/*")

        # No task-role secret grants: ECS injects container secrets through the
        # EXECUTION role (CDK grants it via ecs.Secret.from_secrets_manager);
        # the app never calls Secrets Manager at runtime, so a task-role grant
        # would only widen what a compromised process could read.

        # The API sends one message per document to the ingest queue
        # (SendMessage, GetQueueAttributes, GetQueueUrl; nothing else).
        ingest.queue.grant_send_messages(be_task_def.task_role)

        ops_db_secret = secretsmanager.Secret(
            self,
            "OpsDbSecret",
            secret_name="policy_atlas_v3/ops_db",
            description="Credentials for the Policy Atlas ops database login",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "pa_ops"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=40,
            ),
        )

        migration_task_def = ecs.FargateTaskDefinition(
            self, "PolicyAtlasMigrationTaskDef",
            cpu=512,
            memory_limit_mib=1024,
            family="policy-atlas-v3-migrate",
        )
        migration_task_def.add_container("policy-atlas-migration-container",
            image=backend_image,
            # The login sync is idempotent and re-asserts the previous state on
            # failure, so it never fails the task after a committed migration:
            # a public outage must not follow an ops-only step.
            # deploy.sh checks the secret before starting ops.
            command=["sh", "-c", "alembic upgrade head && (python -m policy_atlas.ops.db_role sync || echo 'WARN: ops login sync failed; the ops service keeps its previous login')"],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="Migrate",
                                            log_group=shared_log_group),
            environment={"OPS_DB_SECRET_ARN": ops_db_secret.secret_arn},
            secrets={
                "DATABASE_URL": ecs.Secret.from_secrets_manager(
                    db_secret, field="db_connection_string"
                ),
            },
        )
        migration_task_def.task_role.add_to_principal_policy(iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"],
            resources=[ops_db_secret.secret_arn],
        ))

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
                # /healthz only proves the process is up. /readyz also opens a
                # database connection, so a bad database secret would make the
                # load balancer kill every task in a loop. deploy.sh checks
                # /readyz once after the rollout instead.
                path="/healthz",
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

        # --- Ops service ---
        # The sign-in addresses the browser talks to; both sites' Content
        # Security Policies list them.
        cognito_hosted_domains = [
            f"https://{pa_app_config['cognito_domain_prefix']}.auth."
            f"{self.region}.amazoncognito.com"
        ]
        if auth_domain:
            # ADR 0049: our own sign-in address, beside the prefix address.
            cognito_hosted_domains.append(f"https://{auth_domain}")
        # This runs the same image as the public API, but with only the credentials
        # and permissions needed by the operator-facing application.
        ops_task_def = ecs.FargateTaskDefinition(
            self,
            "PolicyAtlasOpsTaskDef",
            cpu=ops_config["cpu"],
            memory_limit_mib=ops_config["memory_limit_mib"],
            family="policy-atlas-v3-ops",
        )
        ops_task_def.add_container(
            "policy-atlas-ops-container",
            image=backend_image,
            cpu=ops_config["cpu"],
            memory_limit_mib=ops_config["memory_limit_mib"],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="PolicyAtlasOps", log_group=shared_log_group),
            environment={
                "OIDC_ISSUER": auth.issuer,
                "OIDC_JWKS_URL": auth.jwks_url,
                "OIDC_CLIENT_ID": auth.client_id_value,
                "APP_ORIGIN": f"https://{ops_domain}",
                # The public site, for the address of an invite link.
                "PUBLIC_APP_ORIGIN": f"https://{domain_name}",
                "POLICY_ATLAS_SERVICE_ROLE": "ops",
                "POLICY_ATLAS_SELF_SIGNUP": "1" if self_signup_config["enabled"] else "0",
                "POLICY_ATLAS_SELF_SIGNUP_MAX_PER_HOUR": str(self_signup_config["max_per_hour"]),
                "OPS_UI_DIR": "/app/ops-ui",
                # The ops pages' Content Security Policy (ADR 0048). The ops
                # service sends it itself, because CloudFront does not serve
                # these pages. csp_mode governs both sites.
                "OPS_CONTENT_SECURITY_POLICY": content_security_policy(
                    api_origin=None,
                    cognito_region=self.region,
                    cognito_hosted_domains=cognito_hosted_domains,
                    waf_captcha=False,
                    frame_ancestors="'none'",
                ),
                "OPS_CSP_MODE": pa_app_config.get("csp_mode") or "",
                # The same limits as the API, so the ops pages' resolved
                # limits agree with /me.
                "RUNS_PER_USER": str(be_config["runs_per_user"]),
                "TASK_QUOTA_PER_YEAR": str(be_config["task_quota_per_year"]),
                "DB_POOL_SIZE": "5",
                "DB_MAX_OVERFLOW": "5",
                "FORWARDED_ALLOW_IPS": vpc.vpc_cidr_block,
                "LOG_LEVEL": "INFO",
                "LOG_FORMAT": "json",
                "PA_BACKEND_MODE": "stub",
            },
            secrets={"DATABASE_URL": ecs.Secret.from_secrets_manager(
                ops_db_secret, field="db_connection_string"
            )},
            port_mappings=[ecs.PortMapping(
                container_port=be_config["internal_port"], protocol=ecs.Protocol.TCP
            )],
            stop_timeout=Duration.seconds(10),
        )
        ops_task_def.task_role.add_to_principal_policy(iam.PolicyStatement(
            actions=[
                "cognito-idp:AdminCreateUser", "cognito-idp:AdminGetUser",
                "cognito-idp:ListUsers", "cognito-idp:AdminDisableUser",
                "cognito-idp:AdminUserGlobalSignOut", "cognito-idp:AdminEnableUser",
            ],
            resources=[auth.user_pool.user_pool_arn],
        ))
        ops_service = ecs.FargateService(
            self,
            "PolicyAtlasOpsService",
            cluster=cluster,
            task_definition=ops_task_def,
            service_name="policy-atlas-v3-ops-service",
            # Template-pinned at zero like the API's: deploy.sh scales it to
            # ops.desired_count only after the migration, the login sync and
            # the public service are done.
            desired_count=0,
            min_healthy_percent=0,
            max_healthy_percent=100,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            security_groups=[be_sg],
            assign_public_ip=False,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )
        ops_target_group = elbv2.ApplicationTargetGroup(
            self,
            "OpsTargetGroup",
            target_group_name="pa-v3-ops-tg",
            vpc=vpc,
            port=be_config["internal_port"],
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/healthz", interval=Duration.seconds(30), timeout=Duration.seconds(5),
                healthy_threshold_count=2, unhealthy_threshold_count=5,
                healthy_http_codes="200-399",
            ),
            targets=[ops_service.load_balancer_target(
                container_name="policy-atlas-ops-container",
                container_port=be_config["internal_port"], protocol=ecs.Protocol.TCP,
            )],
        )
        ops_allowed_cidrs = ssm.StringListParameter.value_for_typed_list_parameter(
            self, ops_config["allowed_cidrs_parameter_name"]
        )
        for rule_index, first_cidr in enumerate(range(0, ops_allowlist_size, 4)):
            rule_cidrs = [
                Fn.select(cidr_index, ops_allowed_cidrs)
                for cidr_index in range(first_cidr, min(first_cidr + 4, ops_allowlist_size))
            ]
            shared_listener.add_target_groups(
                "OpsListenerRule" if rule_index == 0 else f"OpsListenerRule{rule_index + 1}",
                target_groups=[ops_target_group],
                priority=30 + rule_index,
                conditions=[
                    elbv2.ListenerCondition.host_headers([ops_domain]),
                    elbv2.ListenerCondition.source_ips(rule_cidrs),
                ],
            )
        r53.ARecord(
            self,
            "OpsAliasRecord",
            zone=hosted_zone,
            record_name=ops_config["subdomain"],
            target=r53.RecordTarget.from_alias(r53_targets.LoadBalancerTarget(shared_alb)),
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
        # Task 064c / ADR 0048: application security headers on every response.
        security_headers = SecurityHeaders(
            self,
            "SecurityHeaders",
            csp_mode=pa_app_config.get("csp_mode"),
            api_origin=f"https://{be_domain}",
            cognito_region=self.region,
            cognito_hosted_domains=cognito_hosted_domains,
            waf_captcha=be_config["waf"]["captcha"],
        ).policy
        # www is a courtesy alias only: 301 to the apex so Cognito callback
        # URLs and the API's single-origin CORS stay canonical (#53 follow-up).
        www_redirect = cloudfront.Function(self, "WwwRedirectFunction",
            code=cloudfront.FunctionCode.from_inline(
                "function handler(event) {\n"
                "    var request = event.request;\n"
                "    var host = request.headers.host.value;\n"
                "    if (host.indexOf('www.') === 0) {\n"
                "        var qs = '';\n"
                "        var keys = Object.keys(request.querystring);\n"
                "        for (var i = 0; i < keys.length; i++) {\n"
                "            var q = request.querystring[keys[i]];\n"
                "            qs += (qs ? '&' : '?') + keys[i] + (q.value ? '=' + q.value : '');\n"
                "        }\n"
                "        return {\n"
                "            statusCode: 301,\n"
                "            statusDescription: 'Moved Permanently',\n"
                "            headers: {location: {value: 'https://' + host.slice(4) + request.uri + qs}}\n"
                "        };\n"
                "    }\n"
                "    return request;\n"
                "}\n"
            ),
        )
        www_redirect_association = cloudfront.FunctionAssociation(
            function=www_redirect,
            event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
        )
        distribution = cloudfront.Distribution(self, "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=frontend_origin,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                response_headers_policy=security_headers,
                function_associations=[www_redirect_association],
            ),
            additional_behaviors={
                "/index.html": cloudfront.BehaviorOptions(
                    origin=frontend_origin,
                    cache_policy=index_html_cache_policy,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=security_headers,
                    function_associations=[www_redirect_association],
                ),
            },
            certificate=certificate,
            # Explicit pin of today's default (oldest allowed TLS version, the
            # encryption protocol for HTTPS) so it cannot drift.
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            domain_names=[domain_name, f"www.{domain_name}"],
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

        r53.ARecord(self, "FrontendARecordWWW",
            zone=hosted_zone,
            record_name='www',
            target=r53.RecordTarget.from_alias(r53_targets.CloudFrontTarget(distribution)),
        )

        r53.AaaaRecord(self, "FrontendAaaaRecord",
            zone=hosted_zone,
            target=r53.RecordTarget.from_alias(r53_targets.CloudFrontTarget(distribution)),
        )

        r53.AaaaRecord(self, "FrontendAaaaRecordWWW",
            zone=hosted_zone,
            record_name='www',
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

        ssm.StringParameter(self, "OpsServiceNameParameter",
            parameter_name="/policy_atlas_v3/deploy/ops_service_name",
            string_value="policy-atlas-v3-ops-service",
        )
        ssm.StringParameter(self, "OpsTargetGroupArnParameter",
            parameter_name="/policy_atlas_v3/deploy/ops_target_group_arn",
            string_value=ops_target_group.target_group_arn,
        )
        ssm.StringParameter(self, "OpsDbSecretArnParameter",
            parameter_name="/policy_atlas_v3/deploy/ops_db_secret_arn",
            string_value=ops_db_secret.secret_arn,
        )
        ssm.StringParameter(self, "OpsDomainParameter",
            parameter_name="/policy_atlas_v3/deploy/ops_domain",
            string_value=ops_domain,
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
