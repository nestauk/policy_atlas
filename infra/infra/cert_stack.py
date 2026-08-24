"""us-east-1 certificate stack for the Policy Atlas v3 CloudFront distribution."""

from aws_cdk import Stack, aws_certificatemanager as acm, aws_route53 as r53


class PaV3CertStack(Stack):
    """Create the CloudFront certificate validated in the configured hosted zone.

    Args:
        scope: Construct scope in which to define the stack.
        construct_id: CloudFormation stack identifier.
        network_config: Network configuration containing ``public_domain_name``.
        kwargs: Standard CDK stack properties.
    """

    def __init__(
        self,
        scope,
        construct_id: str,
        network_config: dict,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        domain_name = network_config["public_domain_name"]
        hosted_zone = r53.HostedZone.from_lookup(
            self,
            "HostedZone",
            domain_name=domain_name,
        )
        self.certificate = acm.Certificate(
            self,
            "FrontendCertificate",
            domain_name=domain_name,
            subject_alternative_names=[f"www.{domain_name}"],
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )
