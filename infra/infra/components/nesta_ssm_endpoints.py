"""SSM connectivity policies and their production VPC endpoints."""

from dataclasses import dataclass
from enum import Enum

from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class SsmConnectivityMode(Enum):
    """Supported paths from a managed node to Systems Manager."""

    NAT = "nat"
    INTERFACE_ENDPOINTS = "interface_endpoints"


@dataclass(frozen=True)
class SsmConnectivity:
    """Describe the SSM network path a managed node must use."""

    mode: SsmConnectivityMode
    managed_node_security_group: ec2.ISecurityGroup | None = None

    def __post_init__(self) -> None:
        """Validate that the selected mode has exactly the required resources."""
        if not isinstance(self.mode, SsmConnectivityMode):
            raise ValueError("mode must be a SsmConnectivityMode value.")
        has_security_group = self.managed_node_security_group is not None
        if self.mode is SsmConnectivityMode.NAT and has_security_group:
            raise ValueError("NAT SSM connectivity must not provide a security group.")
        if (
            self.mode is SsmConnectivityMode.INTERFACE_ENDPOINTS
            and not has_security_group
        ):
            raise ValueError(
                "Interface-endpoint SSM connectivity requires a managed-node "
                "security group."
            )

    @classmethod
    def via_nat(cls) -> "SsmConnectivity":
        """Create an internet/NAT-backed SSM connectivity policy.

        Returns:
            Connectivity that permits the managed node to use public SSM
            endpoints through its subnet's default route.
        """
        return cls(mode=SsmConnectivityMode.NAT)

    @classmethod
    def via_interface_endpoints(
        cls,
        managed_node_security_group: ec2.ISecurityGroup,
    ) -> "SsmConnectivity":
        """Create a PrivateLink-backed SSM connectivity policy.

        Args:
            managed_node_security_group: Security group pre-wired to reach the
                SSM interface endpoint security group on HTTPS.

        Returns:
            Connectivity that attaches the supplied security group to the
            managed node.

        Raises:
            ValueError: If no managed-node security group is supplied.
        """
        if not managed_node_security_group:
            raise ValueError("managed_node_security_group is required.")
        return cls(
            mode=SsmConnectivityMode.INTERFACE_ENDPOINTS,
            managed_node_security_group=managed_node_security_group,
        )


class SsmVpcEndpoints(Construct):
    """Create the core interface endpoints used by current SSM Agent versions.

    This construct creates the following endpoints in the given VPC:
    - com.amazonaws.<region>.ssm
    - com.amazonaws.<region>.ssmmessages

    It also creates a managed-node security group already wired to the endpoint
    security group. Consumers attach that group rather than modifying endpoint
    rules across stack boundaries.
    """

    def __init__(self, scope: Construct, id: str, vpc: ec2.IVpc) -> None:
        """Initialize the SSM VPC endpoints.

        Args:
            scope: Construct scope.
            id: Construct identifier.
            vpc: VPC in which to create the endpoints.

        Raises:
            ValueError: If no VPC is supplied.
        """
        super().__init__(scope, id)

        if not vpc:
            raise ValueError("VPC is required for SSM interface endpoints.")

        self.endpoint_sg = ec2.SecurityGroup(
            self,
            f"{id}-SSMEndpointSG",
            vpc=vpc,
            description="Accept HTTPS from approved SSM managed nodes",
            allow_all_outbound=False,
        )

        self.managed_node_sg = ec2.SecurityGroup(
            self,
            f"{id}-ManagedNodeEndpointSG",
            vpc=vpc,
            description="Allow managed nodes to reach private SSM endpoints",
            allow_all_outbound=False,
        )

        self.managed_node_sg.add_egress_rule(
            peer=self.endpoint_sg,
            connection=ec2.Port.tcp(443),
            description="Allow managed nodes to connect to SSM endpoints",
        )

        self.endpoint_sg.add_ingress_rule(
            peer=self.managed_node_sg,
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS from approved SSM managed nodes",
        )

        for name, service in (
            ("SSM", ec2.InterfaceVpcEndpointAwsService.SSM),
            ("SSMMessages", ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES),
        ):
            ec2.InterfaceVpcEndpoint(
                self,
                f"{id}-{name}Endpoint",
                vpc=vpc,
                service=service,
                security_groups=[self.endpoint_sg],
                subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                ),
                private_dns_enabled=True,
            )

        self.connectivity = SsmConnectivity.via_interface_endpoints(
            self.managed_node_sg
        )
