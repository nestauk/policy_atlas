"""Import the network stack's shared ALB into a consumer stack through SSM."""

from dataclasses import dataclass

from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ssm as ssm,
)

SHARED_ALB_SSM_PREFIX = "/policy_atlas_v3/shared_alb"


@dataclass(frozen=True)
class SharedAlbImports:
    """Deploy-time references to the shared application load balancer.

    Attributes:
        security_group: The ALB's security group, the peer for service ingress.
        load_balancer: The ALB itself, the target for Route 53 alias records.
        listener: The shared HTTPS listener that host-based rules attach to.
    """

    security_group: ec2.ISecurityGroup
    load_balancer: elbv2.IApplicationLoadBalancer
    listener: elbv2.IApplicationListener


def import_shared_alb(stack: Stack) -> SharedAlbImports:
    """Import the shared ALB, its security group and HTTPS listener from SSM.

    Every identifier resolves at deploy time through an
    ``AWS::SSM::Parameter::Value`` template parameter, so consumer templates
    never embed physical IDs. The imports are created directly on the stack
    under fixed construct IDs: an imported security group names the ingress
    rules added against it after its own construct path, so moving or renaming
    these would rename live ``AWS::EC2::SecurityGroupIngress`` resources.

    Args:
        stack: The consumer stack that attaches to the shared ALB.

    Returns:
        The imported security group, load balancer and HTTPS listener.
    """

    def parameter(name: str) -> str:
        return ssm.StringParameter.value_for_string_parameter(
            stack,
            parameter_name=f"{SHARED_ALB_SSM_PREFIX}/{name}",
        )

    load_balancer_arn = parameter("arn")
    security_group_id = parameter("security_group_id")
    dns_name = parameter("dns_name")
    canonical_hosted_zone_id = parameter("canonical_hosted_zone_id")
    listener_arn = parameter("https_listener_arn")

    security_group = ec2.SecurityGroup.from_security_group_id(
        stack,
        "SharedALBSG",
        security_group_id=security_group_id,
        allow_all_outbound=False,
    )
    load_balancer = (
        elbv2.ApplicationLoadBalancer.from_application_load_balancer_attributes(
            stack,
            "SharedALB",
            load_balancer_arn=load_balancer_arn,
            security_group_id=security_group_id,
            load_balancer_dns_name=dns_name,
            load_balancer_canonical_hosted_zone_id=canonical_hosted_zone_id,
        )
    )
    listener = elbv2.ApplicationListener.from_application_listener_attributes(
        stack,
        "SharedHTTPSListener",
        listener_arn=listener_arn,
        security_group=security_group,
    )
    return SharedAlbImports(
        security_group=security_group,
        load_balancer=load_balancer,
        listener=listener,
    )
