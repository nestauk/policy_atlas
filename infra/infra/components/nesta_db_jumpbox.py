from aws_cdk import CfnOutput, aws_ec2 as ec2, aws_rds as rds
from constructs import Construct


class NestaDBJumpbox(Construct):
    """Provide IAM-gated access to an RDS database through SSM.

    The construct creates a small Amazon Linux instance with no inbound access.
    Remote mode emits a command that forwards a local port to the database;
    local mode installs PostgreSQL client tools on the instance.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.IVpc,
        db_instance: rds.IDatabaseInstance | None = None,
        db_cluster: rds.IDatabaseCluster | None = None,
        db_sg: ec2.ISecurityGroup | None = None,
        remote_mode: bool = True,
        local_mode: bool = False,
        db_port: int = 5432,
        local_port: int = 15432,
        **kwargs,
    ) -> None:
        """Initialize the jumpbox.

        Args:
            scope: Construct scope.
            id: Construct identifier.
            vpc: VPC containing the jumpbox and database.
            db_instance: RDS instance to connect to, if applicable.
            db_cluster: RDS cluster to connect to, if applicable.
            db_sg: Database security group when no RDS resource is supplied.
            remote_mode: Whether to emit a local port-forwarding command.
            local_mode: Whether to install PostgreSQL client tools.
            db_port: Database port on the remote host.
            local_port: Port exposed on the end user's computer.
            **kwargs: Reserved for future construct options.

        Raises:
            ValueError: If the VPC or database target is invalid, or remote mode
                has no RDS resource from which to obtain an endpoint.
        """
        super().__init__(scope, id)

        if not vpc:
            raise ValueError("VPC is required for the jumpbox.")

        if db_instance and db_cluster:
            raise ValueError(
                "Only one of db_instance or db_cluster should be provided."
            )

        if not db_instance and not db_cluster and not db_sg:
            raise ValueError(
                "At least one of db_instance, db_cluster, or db_sg must be "
                "provided."
            )

        if (db_instance or db_cluster) and db_sg:
            raise ValueError(
                "db_sg should not be provided if db_instance or db_cluster "
                "is provided."
            )

        if remote_mode and not (db_instance or db_cluster):
            raise ValueError(
                "Remote mode requires db_instance or db_cluster so the "
                "port-forwarding command can include the database endpoint."
            )

        # Create a security group for the jumpbox
        self.jumpbox_sg = ec2.SecurityGroup(
            self, f"{id}-SG",
            vpc=vpc,
            description="Security group for the RDS jumpbox",
            allow_all_outbound=True,
        )

        if db_sg:
            database_sg = db_sg
        elif db_instance:
            database_sg = db_instance.connections.security_groups[0]
        elif db_cluster:
            database_sg = db_cluster.connections.security_groups[0]

        # Allow the jumpbox to connect to the database security group
        database_sg.add_ingress_rule(
            peer=self.jumpbox_sg,
            connection=ec2.Port.tcp(db_port),
            description="Allow jumpbox to connect to the database",
        )

        if local_mode:
            # Install PostgreSQL client tools for direct database access.
            user_data = ec2.UserData.for_linux()
            user_data.add_commands(
                "sudo dnf update -y",
                "sudo dnf install -y postgresql15",
            )

        # This host only carries administrative traffic, so keep it small.
        self.jumpbox = ec2.Instance(
            self,
            f"{id}-Instance",
            instance_type=ec2.InstanceType("t4a.nano"),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            security_group=self.jumpbox_sg,
            user_data=user_data if local_mode else None,
            ssm_session_permissions=True,
        )

        if remote_mode:
            if db_instance:
                database_host = db_instance.db_instance_endpoint_address
            else:
                database_host = db_cluster.cluster_endpoint.hostname

            # Emit the port-forwarding command for the user to run locally. The
            # remote-host document forwards through the jumpbox to RDS; the
            # non-remote document would instead target a port on the jumpbox.
            CfnOutput(
                self, f"{id}-PortForwardingCommand",
                value=(
                    "aws ssm start-session "
                    f"--target {self.jumpbox.instance_id} "
                    "--document-name AWS-StartPortForwardingSessionToRemoteHost "
                    f'--parameters host="{database_host}",'
                    f'portNumber="{db_port}",localPortNumber="{local_port}"'
                ),
                description=(
                    "Run locally to forward a port through the jumpbox to the "
                    "database."
                ),
            )
