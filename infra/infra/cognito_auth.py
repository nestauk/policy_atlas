"""Cognito resources for the Policy Atlas v3 single-page application."""

import base64
import json
from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_certificatemanager as acm,
    aws_cognito as cognito,
    aws_route53 as r53,
    aws_route53_targets as r53_targets,
    aws_ssm as ssm,
)
from constructs import Construct

EMAIL_DIRECTORY = Path(__file__).resolve().parents[1] / "email"
BRANDING_DIRECTORY = Path(__file__).resolve().parents[1] / "branding"
SIGN_IN_VALUES = {"mfa": ("off", "app"), "page": ("classic", "managed")}
PAGE_VERSIONS = {
    "classic": cognito.ManagedLoginVersion.CLASSIC_HOSTED_UI,
    "managed": cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN,
}


def _read_email_template(filename: str, *, required_placeholders: tuple[str, ...]) -> str:
    """Read a Cognito email template and check its required placeholders."""
    template = (EMAIL_DIRECTORY / filename).read_text()
    missing = [placeholder for placeholder in required_placeholders if placeholder not in template]
    if missing:
        raise ValueError(f"{filename} is missing required placeholder(s): {', '.join(missing)}")
    return template


def _email_templates(domain_name: str) -> tuple[str, str, str, str]:
    """Read branded templates and replace Policy Atlas URL placeholders."""
    replacements = {
        "__SIGN_IN_URL__": f"https://{domain_name}",
        "__LOGO_URL__": f"https://{domain_name}/brand/email-logo.png",
    }

    def render(filename: str, required_placeholders: tuple[str, ...]) -> str:
        template = _read_email_template(
            filename, required_placeholders=required_placeholders
        )
        for placeholder, value in replacements.items():
            template = template.replace(placeholder, value)
        return template

    return (
        (EMAIL_DIRECTORY / "invitation.subject.txt").read_text().strip(),
        render("invitation.html", ("{username}", "{####}")),
        (EMAIL_DIRECTORY / "verification.subject.txt").read_text().strip(),
        render("verification.html", ("{####}",)),
    )


def _validate_sign_in(sign_in: dict, domain_name: str) -> None:
    """Reject an unknown ``sign_in`` key or value (ADR 0049)."""
    unknown = set(sign_in) - {*SIGN_IN_VALUES, "domain"}
    if unknown:
        raise ValueError(f"sign_in has unknown key(s): {', '.join(sorted(unknown))}")
    for key, allowed in SIGN_IN_VALUES.items():
        if key in sign_in and sign_in[key] not in allowed:
            raise ValueError(f"sign_in.{key} must be one of {allowed}, got {sign_in[key]!r}.")
    if "domain" in sign_in and sign_in["domain"] != f"auth.{domain_name}":
        raise ValueError(f"sign_in.domain must be 'auth.{domain_name}', got {sign_in['domain']!r}.")


def _branding_assets() -> list[cognito.CfnManagedLoginBranding.AssetTypeProperty]:
    """Read the sign-in page images listed in ``branding/assets.json`` as base64."""
    return [
        cognito.CfnManagedLoginBranding.AssetTypeProperty(
            category=asset["category"],
            color_mode=asset["color_mode"],
            extension=asset["extension"],
            bytes=base64.b64encode((BRANDING_DIRECTORY / asset["file"]).read_bytes()).decode(),
        )
        for asset in json.loads((BRANDING_DIRECTORY / "assets.json").read_text())
    ]


class CognitoAuth(Construct):
    """Create the operator-managed Cognito user pool and SPA client.

    Args:
        scope: Construct scope in which to define the authentication resources.
        construct_id: Construct identifier.
        domain_name: Public SPA domain used for callback and logout URLs.
        domain_prefix: Globally unique Cognito hosted-UI domain prefix.
        email: Optional SES sender and branded Cognito email configuration.
        extra_domains: Further web addresses allowed as sign-in callback and logout URLs.
        sign_in: Optional ``sign_in`` block (ADR 0049): ``mfa`` ("off" or "app"),
            ``page`` ("classic" or "managed") and ``domain`` (our own sign-in
            address, ``auth.<domain_name>``). With no block nothing changes.
        auth_certificate: us-east-1 certificate for ``sign_in.domain``.
        hosted_zone: Hosted zone that receives the ``sign_in.domain`` DNS record.

    Raises:
        ValueError: The ``sign_in`` block has an unknown key or value, or names a
            domain without a certificate and hosted zone.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        domain_name: str,
        domain_prefix: str,
        email: dict | None = None,
        extra_domains: list[str] | None = None,
        sign_in: dict | None = None,
        auth_certificate: acm.ICertificate | None = None,
        hosted_zone: r53.IHostedZone | None = None,
    ) -> None:
        super().__init__(scope, construct_id)

        sign_in = sign_in or {}
        _validate_sign_in(sign_in, domain_name)
        auth_domain = sign_in.get("domain")
        if auth_domain and (auth_certificate is None or hosted_zone is None):
            raise ValueError("sign_in.domain needs an auth_certificate and a hosted_zone.")
        # Named on every domain: leaving it out keeps a managed page in place.
        page_version = PAGE_VERSIONS.get(sign_in.get("page"))

        user_pool_kwargs = {}
        if email and email["enabled"]:
            (
                invitation_subject,
                invitation_body,
                verification_subject,
                verification_body,
            ) = _email_templates(domain_name)
            user_pool_kwargs = {
                "email": cognito.UserPoolEmail.with_ses(
                    from_email=email["from_address"],
                    from_name=email["from_name"],
                    ses_region=Stack.of(self).region,
                    ses_verified_domain=email["sender_domain"],
                ),
                "user_invitation": cognito.UserInvitationConfig(
                    email_subject=invitation_subject,
                    email_body=invitation_body,
                ),
                "user_verification": cognito.UserVerificationConfig(
                    email_subject=verification_subject,
                    email_body=verification_body,
                    email_style=cognito.VerificationEmailStyle.CODE,
                ),
            }

        # Authenticator-app codes only: SMS and email codes stay off (ADR 0049).
        if sign_in.get("mfa") == "app":
            user_pool_kwargs["mfa"] = cognito.Mfa.REQUIRED
            user_pool_kwargs["mfa_second_factor"] = cognito.MfaSecondFactor(
                sms=False, otp=True, email=False
            )
        elif sign_in.get("mfa") == "off":
            user_pool_kwargs["mfa"] = cognito.Mfa.OFF

        extra_domains = extra_domains or []

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # Character rules restate Cognito's defaults: once a policy is sent,
            # any rule it omits is off. 30 days because `--invite manual` hands
            # passwords over out of band, which routinely outlasts the 7-day default.
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
                temp_password_validity=Duration.days(30),
            ),
            removal_policy=RemovalPolicy.RETAIN,
            # Blocks accidental deletion of the user pool (and every account in it).
            deletion_protection=True,
            **user_pool_kwargs,
        )

        self.client = cognito.UserPoolClient(
            self,
            "SpaClient",
            user_pool=self.user_pool,
            generate_secret=False,
            # Review-stack hardening (026 step 7) + owner adjudication
            # 30-day refresh kept — normal web-app session
            # expectations beat the shorter-exfiltration-window argument for
            # this audience. NB tokens live in sessionStorage, so a new tab
            # re-runs the hosted-UI round-trip regardless; 30 days mainly
            # keeps a long-lived open tab renewing silently. Explicit values
            # so the synth test pins them; no user-enumeration oracle.
            access_token_validity=Duration.minutes(60),
            refresh_token_validity=Duration.days(30),
            prevent_user_existence_errors=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[
                    f"https://{domain_name}",
                    f"https://{domain_name}/",
                    *[f"https://{domain}" for domain in extra_domains],
                    *[f"https://{domain}/" for domain in extra_domains],
                ],
                logout_urls=[
                    f"https://{domain_name}",
                    f"https://{domain_name}/",
                    *[f"https://{domain}" for domain in extra_domains],
                    *[f"https://{domain}/" for domain in extra_domains],
                ],
            ),
        )

        self.domain = cognito.UserPoolDomain(
            self,
            "HostedUiDomain",
            user_pool=self.user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=domain_prefix,
            ),
            managed_login_version=page_version,
        )
        if auth_domain:
            # Our own sign-in address; the prefix address above keeps working.
            custom_domain = cognito.UserPoolDomain(
                self,
                "CustomDomain",
                user_pool=self.user_pool,
                custom_domain=cognito.CustomDomainOptions(
                    domain_name=auth_domain,
                    certificate=auth_certificate,
                ),
                managed_login_version=page_version,
            )
            r53.ARecord(
                self,
                "CustomDomainRecord",
                zone=hosted_zone,
                record_name=auth_domain,
                target=r53.RecordTarget.from_alias(
                    r53_targets.UserPoolDomainTarget(custom_domain)
                ),
            )
        if sign_in.get("page") == "managed":
            cognito.CfnManagedLoginBranding(
                self,
                "ManagedLoginBranding",
                user_pool_id=self.user_pool.user_pool_id,
                client_id=self.client.user_pool_client_id,
                settings=json.loads((BRANDING_DIRECTORY / "settings.json").read_text()),
                assets=_branding_assets(),
            )

        self.issuer = (
            f"https://cognito-idp.{Stack.of(self).region}.amazonaws.com/"
            f"{self.user_pool.user_pool_id}"
        )
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self.client_id_value = self.client.user_pool_client_id
        self.hosted_domain = self.domain.base_url()

        ssm.StringParameter(
            self,
            "UserPoolIdParameter",
            parameter_name="/policy_atlas_v3/auth/user_pool_id",
            string_value=self.user_pool.user_pool_id,
        )
        ssm.StringParameter(
            self,
            "IssuerParameter",
            parameter_name="/policy_atlas_v3/auth/issuer",
            string_value=self.issuer,
        )
        ssm.StringParameter(
            self,
            "JwksUrlParameter",
            parameter_name="/policy_atlas_v3/auth/jwks_url",
            string_value=self.jwks_url,
        )
        ssm.StringParameter(
            self,
            "ClientIdParameter",
            parameter_name="/policy_atlas_v3/auth/client_id",
            string_value=self.client_id_value,
        )
        ssm.StringParameter(
            self,
            "HostedDomainParameter",
            parameter_name="/policy_atlas_v3/auth/hosted_domain",
            string_value=self.hosted_domain,
        )
