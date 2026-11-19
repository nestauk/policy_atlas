"""Security response headers for the CloudFront web distribution.

Content Security Policy (CSP) tells a browser which places a page may load
content from.  The policy below permits this application, its API, Amazon
Cognito sign-in service, and (when enabled) AWS WAF's CAPTCHA puzzle service.
Permissions-Policy turns off browser features that this application does not
use, such as a camera or microphone.
"""

from aws_cdk import Duration, aws_cloudfront as cloudfront
from constructs import Construct

CSP_MODES = ("report-only", "enforce")
CSP_MAX_LENGTH = 1783
PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=()"
)
POLICY_NAME = "policy-atlas-v3-security-headers"


def content_security_policy(
    *,
    api_origin: str,
    cognito_region: str,
    cognito_hosted_domain: str,
    waf_captcha: bool,
) -> str:
    """Build the Content Security Policy for one environment.

    Args:
        api_origin: The HTTPS origin of the application's API.
        cognito_region: AWS region containing the Cognito user pool.
        cognito_hosted_domain: The HTTPS Cognito hosted sign-in domain.
        waf_captcha: Whether the API firewall shows AWS WAF CAPTCHA puzzles.

    Returns:
        The complete CSP header value in the contract's directive order.
    """
    # The CAPTCHA script comes from <id>.<region>.captcha-sdk.awswaf.com (read
    # from staging 2026-11-19); its own network calls may use other awswaf.com hosts.
    waf_script_source = " https://*.captcha-sdk.awswaf.com" if waf_captcha else ""
    waf_source = " https://*.awswaf.com" if waf_captcha else ""
    cognito_issuer = f"https://cognito-idp.{cognito_region}.amazonaws.com"
    return "; ".join((
        "default-src 'self'",
        f"script-src 'self'{waf_script_source}",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self'",
        (
            f"connect-src 'self' {api_origin} {cognito_issuer} "
            f"{cognito_hosted_domain}{waf_source}"
        ),
        # 'self': the sign-in library's hidden frame ends on our own address.
        f"frame-src 'self' {cognito_hosted_domain}",
        "frame-ancestors 'self'",
        "form-action 'self'",
        "object-src 'none'",
        "base-uri 'self'",
    ))


class SecurityHeaders(Construct):
    """Create the CloudFront policy that sends the application's security headers.

    Args:
        scope: The parent construct, normally the application stack.
        id: The construct id.
        csp_mode: ``"report-only"`` only reports violations in the browser
            console (there is no report collector); ``"enforce"`` blocks them.
        api_origin: The HTTPS origin of the application's API.
        cognito_region: AWS region containing the Cognito user pool.
        cognito_hosted_domain: The HTTPS Cognito hosted sign-in domain.
        waf_captcha: Whether the API firewall enables AWS WAF CAPTCHA.

    Raises:
        ValueError: The CSP mode is missing or unknown, or the resulting header is too long.

    Attributes:
        policy: The CloudFront response headers policy.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        csp_mode: str,
        api_origin: str,
        cognito_region: str,
        cognito_hosted_domain: str,
        waf_captcha: bool,
    ) -> None:
        super().__init__(scope, id)
        if csp_mode not in CSP_MODES:
            raise ValueError(f"csp_mode must be one of {CSP_MODES}, got {csp_mode!r}.")

        csp = content_security_policy(
            api_origin=api_origin,
            cognito_region=cognito_region,
            cognito_hosted_domain=cognito_hosted_domain,
            waf_captcha=waf_captcha,
        )
        if len(csp) > CSP_MAX_LENGTH:
            raise ValueError(f"Content Security Policy exceeds {CSP_MAX_LENGTH} characters.")

        custom_headers = [cloudfront.ResponseCustomHeader(
            header="Permissions-Policy",
            value=PERMISSIONS_POLICY,
            override=True,
        )]
        csp_behavior = None
        if csp_mode == "enforce":
            csp_behavior = cloudfront.ResponseHeadersContentSecurityPolicy(
                content_security_policy=csp,
                override=True,
            )
        else:
            custom_headers.append(cloudfront.ResponseCustomHeader(
                header="Content-Security-Policy-Report-Only",
                value=csp,
                override=True,
            ))

        self.policy = cloudfront.ResponseHeadersPolicy(
            self,
            "Policy",
            response_headers_policy_name=POLICY_NAME,
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                content_security_policy=csp_behavior,
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.SAMEORIGIN,
                    override=False,
                ),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
                    override=False,
                ),
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.seconds(31536000),
                    include_subdomains=True,
                    preload=False,
                    override=False,
                ),
                xss_protection=cloudfront.ResponseHeadersXSSProtection(
                    protection=True,
                    mode_block=True,
                    override=False,
                ),
            ),
            custom_headers_behavior=cloudfront.ResponseCustomHeadersBehavior(
                custom_headers=custom_headers,
            ),
        )
