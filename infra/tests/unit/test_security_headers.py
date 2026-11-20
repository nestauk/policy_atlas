"""Rendered-template checks for task 064c's CloudFront security headers."""
import json
from unittest.mock import patch

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from infra.components.security_headers import (
    CSP_MAX_LENGTH,
    PERMISSIONS_POLICY,
    SecurityHeaders,
    content_security_policy,
)
from infra.cert_stack import PaV3CertStack
from infra.policy_atlas_stack import PolicyAtlasStack
from tests.unit.test_synth import (
    CERT_ENV,
    COUPLING_APP_TEMPLATE,
    DUMMY_IMAGE,
    ENFORCE_APP_TEMPLATE,
    ENV,
    ENV_NAME,
    INFRA_ROOT,
    NETWORK_CONFIG,
    PA_CONFIG,
    PROD_APP_TEMPLATE,
    TEMPLATES,
    _resources,
    _stub_backend_image_asset,
)

STAGING_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://*.eu-west-2.captcha.awswaf.com "
    "https://*.eu-west-2.token.awswaf.com; "
    "style-src 'self' 'unsafe-inline' https://static.captcha.awswaf.com; "
    "img-src 'self' data: blob:; font-src 'self' https://static.captcha.awswaf.com; "
    "media-src 'self' data:; "
    "connect-src 'self' https://api.v3.policyatlas.uk "
    "https://cognito-idp.eu-west-2.amazonaws.com "
    "https://policy-atlas-v3.auth.eu-west-2.amazoncognito.com https://auth.v3.policyatlas.uk "
    "https://*.awswaf.com; "
    "frame-src 'self' https://policy-atlas-v3.auth.eu-west-2.amazoncognito.com "
    "https://auth.v3.policyatlas.uk; "
    "frame-ancestors 'self'; form-action 'self'; object-src 'none'; base-uri 'self'"
)
PROD_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self'; connect-src 'self' "
    "https://api.policyatlas.uk https://cognito-idp.eu-west-2.amazonaws.com "
    "https://policy-atlas-v3-prod.auth.eu-west-2.amazoncognito.com; "
    "frame-src 'self' https://policy-atlas-v3-prod.auth.eu-west-2.amazoncognito.com; "
    "frame-ancestors 'self'; form-action 'self'; object-src 'none'; base-uri 'self'"
)


def _configurations() -> dict:
    return json.loads((INFRA_ROOT / "pa_config.json").read_text())


def _synth(
    *,
    csp_mode: str | None,
    waf_captcha: bool,
    api_origin: str = "https://api.v3.policyatlas.uk",
    prefix: str = "policy-atlas-v3",
) -> dict:
    app = cdk.App()
    stack = cdk.Stack(app, "SecurityHeadersStack")
    SecurityHeaders(
        stack,
        "SecurityHeaders",
        csp_mode=csp_mode,
        api_origin=api_origin,
        cognito_region="eu-west-2",
        cognito_hosted_domains=[
            f"https://{prefix}.auth.eu-west-2.amazoncognito.com"
        ],
        waf_captcha=waf_captcha,
    )
    return Template.from_stack(stack).to_json()


def _policy(template: dict) -> dict:
    _, resource = _resources(template, "AWS::CloudFront::ResponseHeadersPolicy")[0]
    return resource["Properties"]["ResponseHeadersPolicyConfig"]


def _custom_headers(policy: dict) -> dict[str, dict]:
    return {
        header["Header"]: header
        for header in policy["CustomHeadersConfig"]["Items"]
    }


def test_s1_to_s4_report_only_properties_match_each_environment_config():
    configurations = _configurations()
    expected = {"staging": STAGING_CSP, "prod": PROD_CSP}
    for environment, csp in expected.items():
        app_config = configurations[environment]["policy_atlas_config"]
        waf_captcha = app_config["backend"]["waf"]["captcha"]
        template = {"staging": TEMPLATES["app"], "prod": PROD_APP_TEMPLATE}[environment]
        _, distribution = _resources(template, "AWS::CloudFront::Distribution")[0]
        distribution_config = distribution["Properties"]["DistributionConfig"]
        response_policy_id = distribution_config["DefaultCacheBehavior"]["ResponseHeadersPolicyId"]
        assert response_policy_id in [
            {"Ref": logical_id}
            for logical_id, _ in _resources(template, "AWS::CloudFront::ResponseHeadersPolicy")
        ]
        assert all(
            behavior["ResponseHeadersPolicyId"] == response_policy_id
            for behavior in distribution_config["CacheBehaviors"]
        )
        policy = _policy(template)
        security = policy["SecurityHeadersConfig"]
        assert security == {
            "ContentTypeOptions": {"Override": True},
            "FrameOptions": {"FrameOption": "SAMEORIGIN", "Override": False},
            "ReferrerPolicy": {
                "ReferrerPolicy": "strict-origin-when-cross-origin",
                "Override": False,
            },
            "StrictTransportSecurity": {
                "AccessControlMaxAgeSec": 31536000,
                "IncludeSubdomains": True,
                "Preload": False,
                "Override": False,
            },
            "XSSProtection": {"Protection": True, "ModeBlock": True, "Override": False},
        }
        headers = _custom_headers(policy)
        assert headers["Content-Security-Policy-Report-Only"] == {
            "Header": "Content-Security-Policy-Report-Only", "Value": csp, "Override": True,
        }
        assert headers["Permissions-Policy"] == {
            "Header": "Permissions-Policy", "Value": PERMISSIONS_POLICY, "Override": True,
        }
        assert "ContentSecurityPolicy" not in security
        assert ("https://*.awswaf.com" in csp) is waf_captcha
        directives = dict(d.split(" ", 1) for d in csp.split("; "))
        assert ("https://*.eu-west-2.captcha.awswaf.com" in directives["script-src"]) is waf_captcha
        assert ("https://*.eu-west-2.token.awswaf.com" in directives["script-src"]) is waf_captcha
        for name in ("style-src", "font-src"):
            assert ("https://static.captcha.awswaf.com" in directives[name]) is waf_captcha
        assert (directives.get("media-src") == "'self' data:") is waf_captcha


def test_s3_enforce_uses_the_built_in_csp_header_only():
    policy = _policy(ENFORCE_APP_TEMPLATE)
    security = policy["SecurityHeadersConfig"]
    assert security["ContentSecurityPolicy"] == {"ContentSecurityPolicy": STAGING_CSP, "Override": True}
    assert "Content-Security-Policy-Report-Only" not in _custom_headers(policy)


def test_s2_csp_sources_are_complete_and_safe():
    for csp in (STAGING_CSP, PROD_CSP):
        script_src = csp.split("; ")[1]
        assert "'unsafe-inline'" not in script_src
        assert "'unsafe-eval'" not in script_src
        assert len(csp) <= CSP_MAX_LENGTH


def test_s3_rejects_missing_or_unknown_modes():
    for mode in (None, "Enforce"):
        with pytest.raises(ValueError):
            _synth(csp_mode=mode, waf_captcha=False)


@pytest.mark.parametrize("mode", [None, "Enforce"])
def test_s3_whole_stack_rejects_missing_or_unknown_mode_from_config(mode):
    # The value travels the real path: the config dict -> PolicyAtlasStack -> SecurityHeaders.
    # A fresh app, so the half-built stack never joins the shared test app.
    config = json.loads(json.dumps(PA_CONFIG))
    if mode is None:
        del config["policy_atlas_config"]["csp_mode"]
    else:
        config["policy_atlas_config"]["csp_mode"] = mode
    with patch("aws_cdk.aws_ecs.ContainerImage.from_asset", return_value=DUMMY_IMAGE), patch(
        "aws_cdk.aws_ecr_assets.DockerImageAsset", side_effect=_stub_backend_image_asset
    ), pytest.raises(ValueError, match="csp_mode"):
        app = cdk.App(context={"aws:cdk:bundling-stacks": []})
        cert_stack = PaV3CertStack(
            app,
            "PaV3CertStack",
            network_config=NETWORK_CONFIG,
            auth_domain=config["policy_atlas_config"]["sign_in"]["domain"],
            env=CERT_ENV,
            cross_region_references=True,
        )
        PolicyAtlasStack(
            app,
            "PaV3AppStack",
            pa_config=config,
            certificate=cert_stack.certificate,
            auth_certificate=cert_stack.auth_certificate,
            env=ENV,
            env_name=ENV_NAME,
            cross_region_references=True,
        )


def test_s2_rejects_a_csp_over_cloudfront_limit():
    with pytest.raises(ValueError):
        _synth(csp_mode="enforce", waf_captcha=False, prefix="x" * CSP_MAX_LENGTH)


def test_s2_function_adds_waf_source_only_when_captcha_is_enabled():
    common = {
        "api_origin": "https://api.example.test",
        "cognito_region": "eu-west-2",
        "cognito_hosted_domains": ["https://sign-in.example.test"],
    }
    assert "https://*.awswaf.com" in content_security_policy(**common, waf_captcha=True)
    assert "awswaf.com" not in content_security_policy(**common, waf_captcha=False)


def test_s2_cognito_domain_config_couples_the_user_pool_and_csp():
    _, domain = _resources(COUPLING_APP_TEMPLATE, "AWS::Cognito::UserPoolDomain")[0]
    assert domain["Properties"]["Domain"] == "pa-csp-coupling-test"
    policy = _policy(COUPLING_APP_TEMPLATE)
    csp = _custom_headers(policy)["Content-Security-Policy-Report-Only"]["Value"]
    hosted_domain = "https://pa-csp-coupling-test.auth.eu-west-2.amazoncognito.com"
    assert hosted_domain in csp.split("connect-src ", maxsplit=1)[1]
    assert f"frame-src 'self' {hosted_domain}" in csp
