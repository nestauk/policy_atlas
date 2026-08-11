"""Reusable SSM jumpbox for tightly scoped database access."""

from aws_cdk import CfnOutput, aws_ec2 as ec2, aws_rds as rds, aws_ssm as ssm
from constructs import Construct

from .nesta_ssm_endpoints import SsmConnectivity, SsmConnectivityMode


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
        ssm_connectivity: SsmConnectivity,
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
            ssm_connectivity: Network path the SSM Agent must use.
            db_instance: RDS instance to connect to, if applicable.
            db_cluster: RDS cluster to connect to, if applicable.
            db_sg: Database security group override. Required when no RDS
                resource is supplied.
            remote_mode: Whether to emit a local port-forwarding command.
            local_mode: Whether to install PostgreSQL client tools.
            db_port: Database port on the remote host.
            local_port: Port exposed on the end user's computer.
            **kwargs: Reserved for future construct options.

        Raises:
            ValueError: If the modes, ports, VPC, or database target are invalid.
        """
        super().__init__(scope, id)

        if not vpc:
            raise ValueError("VPC is required for the jumpbox.")

        if not remote_mode and not local_mode:
            raise ValueError("At least one of remote_mode or local_mode is required.")

        for port_name, port in (("db_port", db_port), ("local_port", local_port)):
            if (
                isinstance(port, bool)
                or not isinstance(port, int)
                or not 1 <= port <= 65535
            ):
                raise ValueError(f"{port_name} must be an integer from 1 to 65535.")

        if db_instance and db_cluster:
            raise ValueError(
                "Only one of db_instance or db_cluster should be provided."
            )

        if not db_instance and not db_cluster and not db_sg:
            raise ValueError(
                "At least one of db_instance, db_cluster, or db_sg must be "
                "provided."
            )

        if not ssm_connectivity:
            raise ValueError("ssm_connectivity is required for the jumpbox.")

        if remote_mode and not (db_instance or db_cluster):
            raise ValueError(
                "Remote mode requires db_instance or db_cluster so the "
                "port-forwarding command can include the database endpoint."
            )
        if (
            local_mode
            and ssm_connectivity.mode is SsmConnectivityMode.INTERFACE_ENDPOINTS
        ):
            raise ValueError(
                "local_mode requires package-repository egress in addition to "
                "the core SSM interface endpoints."
            )

        database_host: str | None = None
        if remote_mode:
            if db_instance:
                database_host = db_instance.db_instance_endpoint_address
            else:
                database_host = db_cluster.cluster_endpoint.hostname
            if not database_host:
                raise ValueError(
                    "Remote mode requires the database target to expose an endpoint."
                )

        if db_sg:
            database_sg = db_sg
        else:
            database_connections = (
                db_instance.connections if db_instance else db_cluster.connections
            )
            if not database_connections.security_groups:
                raise ValueError(
                    "The database target exposes no security group; provide db_sg "
                    "as an explicit override."
                )
            database_sg = database_connections.security_groups[0]

        # Create a security group for the jumpbox
        self.jumpbox_sg = ec2.SecurityGroup(
            self,
            f"{id}-SG",
            vpc=vpc,
            description="Security group for the RDS jumpbox",
            allow_all_outbound=False,
        )

        # Security groups need both the source egress and destination ingress
        # halves of this connection when jumpbox outbound is deny-by-default.
        self.jumpbox_sg.add_egress_rule(
            peer=database_sg,
            connection=ec2.Port.tcp(db_port),
            description="Allow jumpbox to connect to the database",
        )
        database_sg.add_ingress_rule(
            peer=self.jumpbox_sg,
            connection=ec2.Port.tcp(db_port),
            description="Allow jumpbox to connect to the database",
        )

        # NAT mode uses public SSM endpoints. Interface-endpoint mode attaches
        # a pre-wired client SG after the instance is created below.
        if ssm_connectivity.mode is SsmConnectivityMode.NAT:
            self.jumpbox_sg.add_egress_rule(
                peer=ec2.Peer.any_ipv4(),
                connection=ec2.Port.tcp(443),
                description="Allow jumpbox to connect to the internet for SSM",
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
            instance_type=ec2.InstanceType("t4g.nano"),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(
                cpu_type=ec2.AmazonLinuxCpuType.ARM_64,
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            associate_public_ip_address=False,
            require_imdsv2=True,
            security_group=self.jumpbox_sg,
            user_data=user_data if local_mode else None,
            ssm_session_permissions=True,
        )

        if ssm_connectivity.mode is SsmConnectivityMode.INTERFACE_ENDPOINTS:
            managed_node_sg = ssm_connectivity.managed_node_security_group
            if managed_node_sg is None:
                raise ValueError(
                    "Interface-endpoint connectivity has no managed-node "
                    "security group."
                )
            self.jumpbox.add_security_group(managed_node_sg)

        self.port_forward_document: ssm.CfnDocument | None = None
        if remote_mode:
            self.port_forward_document = ssm.CfnDocument(
                self,
                f"{id}-DatabasePortForwardDocument",
                document_type="Session",
                document_format="JSON",
                target_type="/AWS::EC2::Instance",
                update_method="NewVersion",
                content={
                    "schemaVersion": "1.0",
                    "description": (
                        "Forward a local port only to the linked database through "
                        "the jumpbox."
                    ),
                    "sessionType": "Port",
                    "parameters": {
                        "localPortNumber": {
                            "type": "String",
                            "description": "Port to open on the engineer's computer",
                            "default": str(local_port),
                            "allowedPattern": (
                                "^([1-9][0-9]{0,3}|[1-5][0-9]{4}|"
                                "6[0-4][0-9]{3}|65[0-4][0-9]{2}|"
                                "655[0-2][0-9]|6553[0-5])$"
                            ),
                        }
                    },
                    "properties": {
                        "type": "LocalPortForwarding",
                        "host": database_host,
                        "portNumber": str(db_port),
                        "localPortNumber": "{{ localPortNumber }}",
                    },
                },
            )

            # The custom document fixes the remote host and database port. Its
            # default keeps the common command parameter-free; callers may
            # override only localPortNumber when their preferred port is busy.
            CfnOutput(
                self,
                f"{id}-PortForwardingCommand",
                value=(
                    "aws ssm start-session "
                    f"--target {self.jumpbox.instance_id} "
                    f"--document-name {self.port_forward_document.ref}"
                ),
                description=(
                    "Run locally to forward a port through the jumpbox to the "
                    "database."
                ),
            )
