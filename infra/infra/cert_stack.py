"""us-east-1 certificate stack for the Policy Atlas v3 CloudFront distribution and sign-in address."""

from aws_cdk import Stack, aws_certificatemanager as acm, aws_route53 as r53


class PaV3CertStack(Stack):
    """Create the CloudFront certificate validated in the configured hosted zone.

    Args:
        scope: Construct scope in which to define the stack.
        construct_id: CloudFormation stack identifier.
        network_config: Network configuration containing ``public_domain_name``.
        auth_domain: Our own sign-in address (``sign_in.domain``, ADR 0049); when
            set, a second certificate for it is created as ``auth_certificate``.
        kwargs: Standard CDK stack properties.
    """

    def __init__(
        self,
        scope,
        construct_id: str,
        network_config: dict,
        auth_domain: str | None = None,
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
        # Cognito's custom domain also needs its certificate in us-east-1.
        self.auth_certificate = None
        if auth_domain:
            self.auth_certificate = acm.Certificate(
                self,
                "AuthCertificate",
                domain_name=auth_domain,
                validation=acm.CertificateValidation.from_dns(hosted_zone),
            )
