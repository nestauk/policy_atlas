"""Infrastructure for the staging Policy Atlas analytics service."""

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_ec2 as ec2,
    aws_ecr_assets as ecr_assets,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    aws_rds as rds,
    aws_route53 as r53,
    aws_route53_targets as r53_targets,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
)
from constructs import Construct


class PaV3AnalyticsStack(Stack):
    """Deploy a private Metabase service and its application database.

    The stack intentionally creates only a network path to the Policy Atlas
    database. A curated read role and its grants belong to a separately
    approved data-access change.

    Args:
        scope: Parent CDK construct.
        id: Logical stack identifier.
        metabase_config: Environment-specific Metabase configuration.
        env_name: Deployment environment name.
        **kwargs: Additional CDK stack properties.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        metabase_config: dict,
        env_name: str,
        **kwargs,
    ) -> None:
        """Initialize the Metabase resources.

        Args:
            scope: Parent CDK construct.
            id: Logical stack identifier.
            metabase_config: Environment-specific Metabase configuration.
            env_name: Deployment environment name.
            **kwargs: Additional CDK stack properties.
        """
        super().__init__(scope, id, **kwargs)

        container_config = metabase_config["container"]
        database_config = metabase_config["database"]
        domain_name = metabase_config["domain_name"]
        metabase_domain = (
            f"{metabase_config['metabase_subdomain']}.{domain_name}"
        )
        container_port = container_config["internal_port"]
        allowed_source_cidrs = (
            ssm.StringListParameter.value_for_typed_list_parameter(
                self,
                metabase_config["allowed_cidrs_parameter_name"],
            )
        )

        vpc = ec2.Vpc.from_lookup(
            self,
            "VPC",
            region=metabase_config["aws_region"],
            vpc_name=f"policy-atlas-v3-vpc-{env_name}",
        )
        hosted_zone = r53.HostedZone.from_lookup(
            self,
            "HostedZone",
            domain_name=domain_name,
        )

        shared_alb_arn = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name="/policy_atlas_v3/shared_alb/arn",
        )
        shared_alb_sg_id = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name="/policy_atlas_v3/shared_alb/security_group_id",
        )
        shared_alb_dns = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name="/policy_atlas_v3/shared_alb/dns_name",
        )
        shared_alb_zone_id = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name=(
                "/policy_atlas_v3/shared_alb/canonical_hosted_zone_id"
            ),
        )
        shared_listener_arn = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name="/policy_atlas_v3/shared_alb/https_listener_arn",
        )

        shared_alb_sg = ec2.SecurityGroup.from_security_group_id(
            self,
            "SharedALBSG",
            security_group_id=shared_alb_sg_id,
            allow_all_outbound=False,
        )
        shared_alb = (
            elbv2.ApplicationLoadBalancer
            .from_application_load_balancer_attributes(
                self,
                "SharedALB",
                load_balancer_arn=shared_alb_arn,
                security_group_id=shared_alb_sg_id,
                load_balancer_dns_name=shared_alb_dns,
                load_balancer_canonical_hosted_zone_id=shared_alb_zone_id,
            )
        )
        shared_listener = (
            elbv2.ApplicationListener
            .from_application_listener_attributes(
                self,
                "SharedHTTPSListener",
                listener_arn=shared_listener_arn,
                security_group=shared_alb_sg,
            )
        )

        metabase_security_group = ec2.SecurityGroup(
            self,
            "MetabaseSecurityGroup",
            vpc=vpc,
            description="Policy Atlas Metabase service",
            allow_all_outbound=True,
        )
        metabase_security_group.add_ingress_rule(
            shared_alb_sg,
            ec2.Port.tcp(container_port),
            "Allow the shared ALB to reach Metabase",
        )

        metabase_db_security_group = ec2.SecurityGroup(
            self,
            "MetabaseDatabaseSecurityGroup",
            vpc=vpc,
            description="Policy Atlas Metabase application database",
            allow_all_outbound=False,
        )
        metabase_db_security_group.add_ingress_rule(
            metabase_security_group,
            ec2.Port.tcp(5432),
            "Allow Metabase to reach its application database",
        )

        policy_atlas_db_sg_id = (
            ssm.StringParameter.value_for_string_parameter(
                self,
                parameter_name="/policy_atlas_v3/db/security_group_id",
            )
        )
        policy_atlas_db_security_group = (
            ec2.SecurityGroup.from_security_group_id(
                self,
                "PolicyAtlasDatabaseSecurityGroup",
                security_group_id=policy_atlas_db_sg_id,
                allow_all_outbound=False,
            )
        )
        policy_atlas_db_security_group.add_ingress_rule(
            metabase_security_group,
            ec2.Port.tcp(5432),
            "Allow Metabase network access for a future curated read role",
        )

        metabase_database = rds.DatabaseInstance(
            self,
            "MetabaseDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_17_7,
            ),
            instance_type=ec2.InstanceType(database_config["instance_size"]),
            instance_identifier=f"policy-atlas-v3-metabase-{env_name}",
            database_name="metabase",
            credentials=rds.Credentials.from_generated_secret("metabase"),
            allocated_storage=database_config["allocated_storage"],
            max_allocated_storage=database_config["max_allocated_storage"],
            storage_type=rds.StorageType.GP3,
            storage_encrypted=True,
            multi_az=database_config["multi_az"],
            publicly_accessible=False,
            deletion_protection=True,
            delete_automated_backups=False,
            backup_retention=Duration.days(
                database_config["backup_retention_days"]
            ),
            copy_tags_to_snapshot=True,
            auto_minor_version_upgrade=True,
            engine_lifecycle_support=(
                rds.EngineLifecycleSupport
                .OPEN_SOURCE_RDS_EXTENDED_SUPPORT_DISABLED
            ),
            removal_policy=RemovalPolicy.SNAPSHOT,
            cloudwatch_logs_exports=["postgresql"],
            cloudwatch_logs_retention=logs.RetentionDays.ONE_MONTH,
            parameters={"rds.force_ssl": "1"},
            security_groups=[metabase_db_security_group],
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
        )
        if metabase_database.secret is None:
            raise ValueError("Metabase database credentials secret was not created")

        encryption_secret = secretsmanager.Secret(
            self,
            "MetabaseEncryptionSecret",
            secret_name=f"policy_atlas_v3/metabase/{env_name}/encryption",
            description="Metabase key for encrypting stored connection details",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True,
                include_space=False,
                password_length=64,
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )

        log_group = logs.LogGroup(
            self,
            "MetabaseLogGroup",
            log_group_name=f"/policy_atlas_v3/metabase/{env_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        cluster = ecs.Cluster(
            self,
            "MetabaseCluster",
            vpc=vpc,
            cluster_name=f"policy-atlas-v3-metabase-{env_name}",
        )
        task_definition = ecs.FargateTaskDefinition(
            self,
            "MetabaseTaskDefinition",
            cpu=container_config["cpu"],
            memory_limit_mib=container_config["memory_limit_mib"],
            family=f"policy-atlas-v3-metabase-{env_name}",
        )
        metabase_image = ecs.ContainerImage.from_asset(
            "metabase",
            build_args={"METABASE_VERSION": container_config["image_tag"]},
            platform=ecr_assets.Platform.LINUX_AMD64,
        )
        container = task_definition.add_container(
            "MetabaseContainer",
            image=metabase_image,
            cpu=container_config["cpu"],
            memory_limit_mib=container_config["memory_limit_mib"],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="Metabase",
                log_group=log_group,
            ),
            environment={
                "JAVA_OPTS": container_config["java_opts"],
                "MB_AI_FEATURES_ENABLED": "false",
                "MB_ANON_TRACKING_ENABLED": "false",
                "MB_APPLICATION_DB_MAX_CONNECTION_POOL_SIZE": str(
                    container_config["application_connection_pool_size"]
                ),
                "MB_CHECK_FOR_UPDATES": "false",
                "MB_DB_AUTOMIGRATE": "true",
                "MB_DB_CONNECTION_URI": (
                    "jdbc:postgresql://"
                    f"{metabase_database.db_instance_endpoint_address}:"
                    f"{metabase_database.db_instance_endpoint_port}/"
                    "metabase?sslmode=require"
                ),
                "MB_JDBC_DATA_WAREHOUSE_MAX_CONNECTION_POOL_SIZE": str(
                    container_config["warehouse_connection_pool_size"]
                ),
                "MB_JETTY_PORT": str(container_port),
                "MB_LOAD_SAMPLE_CONTENT": "false",
                "MB_NO_SURVEYS": "true",
                "MB_SITE_NAME": "Policy Atlas Analytics",
                "MB_SITE_URL": f"https://{metabase_domain}",
            },
            secrets={
                "MB_DB_PASS": ecs.Secret.from_secrets_manager(
                    metabase_database.secret,
                    field="password",
                ),
                "MB_DB_USER": ecs.Secret.from_secrets_manager(
                    metabase_database.secret,
                    field="username",
                ),
                "MB_ENCRYPTION_SECRET_KEY": ecs.Secret.from_secrets_manager(
                    encryption_secret,
                ),
            },
            stop_timeout=Duration.seconds(120),
        )
        container.add_port_mappings(
            ecs.PortMapping(
                container_port=container_port,
                protocol=ecs.Protocol.TCP,
            )
        )

        metabase_service = ecs.FargateService(
            self,
            "MetabaseService",
            cluster=cluster,
            task_definition=task_definition,
            service_name=f"policy-atlas-v3-metabase-{env_name}",
            desired_count=container_config["desired_count"],
            min_healthy_percent=0,
            max_healthy_percent=100,
            availability_zone_rebalancing=(
                ecs.AvailabilityZoneRebalancing.DISABLED
            ),
            health_check_grace_period=Duration.minutes(5),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            security_groups=[metabase_security_group],
            assign_public_ip=False,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
        )

        metabase_target_group = elbv2.ApplicationTargetGroup(
            self,
            "MetabaseTargetGroup",
            target_group_name=f"pa-v3-metabase-{env_name}",
            vpc=vpc,
            port=container_port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            deregistration_delay=Duration.seconds(30),
            health_check=elbv2.HealthCheck(
                path="/api/health",
                healthy_http_codes="200",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=5,
            ),
            targets=[
                metabase_service.load_balancer_target(
                    container_name="MetabaseContainer",
                    container_port=container_port,
                    protocol=ecs.Protocol.TCP,
                )
            ],
        )
        shared_listener.add_target_groups(
            "MetabaseTargetGroupAttachment",
            target_groups=[metabase_target_group],
            priority=20,
            conditions=[
                elbv2.ListenerCondition.host_headers([metabase_domain]),
                elbv2.ListenerCondition.source_ips(allowed_source_cidrs),
            ],
        )

        r53.ARecord(
            self,
            "MetabaseAliasRecord",
            zone=hosted_zone,
            record_name=metabase_config["metabase_subdomain"],
            target=r53.RecordTarget.from_alias(
                r53_targets.LoadBalancerTarget(shared_alb)
            ),
        )
