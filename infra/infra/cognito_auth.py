"""Cognito resources for the Policy Atlas v3 single-page application."""

from aws_cdk import Duration, Stack, RemovalPolicy, aws_cognito as cognito, aws_ssm as ssm
from constructs import Construct


class CognitoAuth(Construct):
    """Create the operator-managed Cognito user pool and SPA client.

    Args:
        scope: Construct scope in which to define the authentication resources.
        construct_id: Construct identifier.
        domain_name: Public SPA domain used for callback and logout URLs.
        domain_prefix: Globally unique Cognito hosted-UI domain prefix.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        domain_name: str,
        domain_prefix: str,
    ) -> None:
        super().__init__(scope, construct_id)

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.client = cognito.UserPoolClient(
            self,
            "SpaClient",
            user_pool=self.user_pool,
            generate_secret=False,
            # Review-stack hardening (026 step 7) + owner adjudication
            # (2026-07-28): 30-day refresh kept — normal web-app session
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
                ],
                logout_urls=[
                    f"https://{domain_name}",
                    f"https://{domain_name}/",
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
