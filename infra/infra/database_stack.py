# Core database stack. Deploys the following resources:
# * RDS Aurora Provisioned Cluster
# This also takes the following extra steps:
# * Creates a Secrets Manager secret to hold the database credentials
# * Stores the database security group ID in SSM Parameter Store for later use
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_ssm as ssm,
    aws_lambda as _lambda,
    triggers,
)

from .components.nesta_db_jumpbox import NestaDBJumpbox


class DatabaseStack(Stack):
    def __init__(self, scope: Stack, id: str,
                 db_config: dict, env_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # LH 08/05/2026: As per PR 172, removed the vpc_id lookup and instead look up the VPC directly.
        # There were dependency problems with the lookup ID step via SSM.
        vpc = ec2.Vpc.from_lookup(self, "VPC", region=db_config['aws_region'],
            vpc_name="policy-atlas-v3-vpc-" + env_name)

        # Create a security group for the RDS cluster.
        db_security_group = ec2.SecurityGroup(self, "DBSecurityGroup",
            vpc=vpc,
            description="Security group for PA DB cluster",
            allow_all_outbound=True
        )

        if db_config["readers"] == 0:
            readers = None
        else:
            readers = []
            for _ in range(db_config["readers"]):
                readers.append(
                    rds.ClusterInstance.provisioned(
                        "PolicyAtlasDBReaderInstance" + str(_),
                        instance_type=ec2.InstanceType(db_config["reader_instance_size"]),
                        instance_identifier=f"policy-atlas-v3-db-reader-{_}",
                    )
                )

        writer = rds.ClusterInstance.provisioned(
            "PolicyAtlasDBWriterInstance",
            instance_type=ec2.InstanceType(db_config["writer_instance_size"]),
            instance_identifier=f"policy-atlas-v3-db-writer",
        )

        # Create the RDS Aurora cluster.
        cluster = rds.DatabaseCluster(self, "PolicyAtlasDBCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_17_7),
            writer=writer,
            readers=readers,
            default_database_name="policy_atlas_db",
            credentials=rds.Credentials.from_generated_secret("dbadmin"),
            removal_policy=RemovalPolicy.SNAPSHOT,
            # Review-stack hardening (026 step 7): encryption at rest, delete
            # guard, 7-day backups. NB StorageEncrypted cannot be toggled in
            # place, and the pinned cluster/instance identifiers mean
            # CloudFormation cannot swap in a replacement either (the
            # create-before-delete collides on the name — the update FAILS).
            # Apply via the one-time destroy→redeploy in DEPLOYMENT.md § 4,
            # scheduled while the DB holds smoke data only.
            storage_encrypted=True,
            deletion_protection=True,
            backup=rds.BackupProps(retention=Duration.days(7)),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            cluster_identifier="policy-atlas-v3-db-cluster",
            security_groups=[db_security_group]
        )

        # --- Load secret Lambda (writes db_connection_string into the RDS secret) ---
        load_secret_function = _lambda.Function(self, "LoadSecretFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="load_secret.load_secret",
            code=_lambda.Code.from_asset("infra/deploy_functions/load_secret"),
            environment={
                "SECRET_NAME": cluster.secret.secret_name
            }
        )

        cluster.secret.grant_read(load_secret_function)
        cluster.secret.grant_write(load_secret_function)

        # --- Triggers: ordering ---
        # LoadSecretTrigger runs after the cluster. There are no task definitions
        # left in this stack for it to execute before.

        triggers.Trigger(self, "LoadSecretTrigger",
            handler=load_secret_function,
            execute_after=[cluster],
        )

        # --- Migration security group ---
        migration_sg = ec2.SecurityGroup(self, "MigrationLambdaSG",
            vpc=vpc,
            description="Security group for DB migration Lambda",
            allow_all_outbound=True
        )

        db_security_group.add_ingress_rule(
            peer=migration_sg,
            connection=ec2.Port.tcp(5432),
            description="Allow migration Lambda to connect to RDS"
        )

        # Allow the fck-nat instance (NetworkStack) to reach Aurora on 5432.
        fck_nat_sg_id = ssm.StringParameter.value_for_string_parameter(self,
            parameter_name="/policy_atlas_v3/network/fck_nat_sg_id")
        fck_nat_sg = ec2.SecurityGroup.from_security_group_id(
            self, "FckNatSG", security_group_id=fck_nat_sg_id,
            allow_all_outbound=False,
        )
        db_security_group.add_ingress_rule(
            peer=fck_nat_sg,
            connection=ec2.Port.tcp(5432),
            description="Allow fck-nat instance to connect to RDS"
        )

        # Provide IAM-gated database access without public ingress.
        NestaDBJumpbox(self, "NestaDBJumpbox",
            vpc=vpc,
            db_cluster=cluster,
            remote_mode=True,
            local_mode=False,
            db_port=5432,
            local_port=15432,
        )

        # --- SSM parameter exports ---

        ssm.StringParameter(self, "DBSecurityGroupParameter",
            parameter_name="/policy_atlas_v3/db/security_group_id",
            string_value=db_security_group.security_group_id
        )

        ssm.StringParameter(self, "DBSecretNameParameter",
            parameter_name="/policy_atlas_v3/db/secret_name",
            string_value=cluster.secret.secret_name
        )

        # The migration SG lives here (this stack owns it); PolicyAtlasStack
        # (B.3) reads it to attach to the one-shot ECS Alembic migration task.
        ssm.StringParameter(self, "MigrationSGParameter",
            parameter_name="/policy_atlas_v3/deploy/migration_sg_id",
            string_value=migration_sg.security_group_id
        )
