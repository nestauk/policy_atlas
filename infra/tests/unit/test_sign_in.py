"""Rendered-template checks for the sign-in settings (ADR 0049)."""
import base64
import json
import os
from unittest.mock import patch

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from infra.cert_stack import PaV3CertStack
from infra.cognito_auth import CognitoAuth, sign_in_block
from infra.policy_atlas_stack import PolicyAtlasStack
from tests.unit.test_synth import (
    CDK_CONTEXT,
    CERT_ENV,
    DUMMY_IMAGE,
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

BASELINE = INFRA_ROOT / "tests" / "unit" / "fixtures" / "sign_in_all_off.json"
BRANDING = INFRA_ROOT / "branding"
SIGN_IN_TYPES = (
    "AWS::Cognito::UserPool",
    "AWS::Cognito::UserPoolClient",
    "AWS::Cognito::UserPoolDomain",
    "AWS::Cognito::ManagedLoginBranding",
    "AWS::CloudFront::ResponseHeadersPolicy",
    "AWS::Route53::RecordSet",
)


def _sign_in_resources(app_template: dict, cert_template: dict) -> dict:
    """Collect what a sign-in change could touch: the pool, client, domains, branding, CSP, DNS records, cert stack."""
    return {
        "app": {
            logical_id: resource
            for resource_type in SIGN_IN_TYPES
            for logical_id, resource in _resources(app_template, resource_type)
        },
        "cert": cert_template,
    }


def test_production_sign_in_resources_equal_baseline():
    # With no `sign_in` block the change adds nothing. Regenerate the baseline only from
    # code that predates the change: UPDATE_SIGN_IN_BASELINE=1 make -C infra test.
    rendered = _sign_in_resources(PROD_APP_TEMPLATE, TEMPLATES["cert"])
    if os.environ.get("UPDATE_SIGN_IN_BASELINE") == "1":
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(rendered, indent=1, sort_keys=True) + "\n")
    assert rendered == json.loads(BASELINE.read_text())


def _synth(sign_in: dict) -> tuple[dict, dict]:
    """Synthesize the staging app and cert stacks with the given ``sign_in`` block."""
    config = json.loads(json.dumps(PA_CONFIG))
    config["policy_atlas_config"]["sign_in"] = sign_in
    with patch("aws_cdk.aws_ecs.ContainerImage.from_asset", return_value=DUMMY_IMAGE), patch(
        "aws_cdk.aws_ecr_assets.DockerImageAsset", side_effect=_stub_backend_image_asset
    ):
        app = cdk.App(context={**CDK_CONTEXT, "aws:cdk:bundling-stacks": []})
        cert_stack = PaV3CertStack(
            app,
            "PaV3CertStack",
            network_config=NETWORK_CONFIG,
            auth_domain=sign_in.get("domain"),
            env=CERT_ENV,
            cross_region_references=True,
        )
        app_stack = PolicyAtlasStack(
            app,
            "PaV3AppStack",
            pa_config=config,
            certificate=cert_stack.certificate,
            auth_certificate=cert_stack.auth_certificate,
            env=ENV,
            env_name=ENV_NAME,
            cross_region_references=True,
        )
    return Template.from_stack(app_stack).to_json(), Template.from_stack(cert_stack).to_json()


AUTH_DOMAIN = "auth.v3.policyatlas.uk"
SYNTHS = {
    "app-managed-domain": _synth({"mfa": "app", "page": "managed", "domain": AUTH_DOMAIN}),
    "app-classic": _synth({"mfa": "app", "page": "classic"}),
    "off-classic": _synth({"mfa": "off", "page": "classic"}),
    "app-classic-domain": _synth({"mfa": "app", "page": "classic", "domain": AUTH_DOMAIN}),
}


def _user_pool(template: dict) -> dict:
    [(_, pool)] = _resources(template, "AWS::Cognito::UserPool")
    return pool["Properties"]


def _domains(template: dict) -> list[dict]:
    return [domain["Properties"] for _, domain in _resources(template, "AWS::Cognito::UserPoolDomain")]


def _csp_directives(template: dict) -> dict[str, str]:
    [(_, policy)] = _resources(template, "AWS::CloudFront::ResponseHeadersPolicy")
    headers = policy["Properties"]["ResponseHeadersPolicyConfig"]["CustomHeadersConfig"]["Items"]
    [csp] = [h["Value"] for h in headers if h["Header"] == "Content-Security-Policy-Report-Only"]
    return dict(directive.split(" ", 1) for directive in csp.split("; "))


@pytest.mark.parametrize("name", ["app-managed-domain", "app-classic"])
def test_app_mfa_requires_authenticator_codes_only(name):
    pool = _user_pool(SYNTHS[name][0])
    assert pool["MfaConfiguration"] == "ON"
    assert pool["EnabledMfas"] == ["SOFTWARE_TOKEN_MFA"]
    assert pool["AccountRecoverySetting"] == {
        "RecoveryMechanisms": [{"Name": "verified_email", "Priority": 1}]
    }


def test_off_mfa_names_mfa_off():
    pool = _user_pool(SYNTHS["off-classic"][0])
    assert pool["MfaConfiguration"] == "OFF"
    assert "EnabledMfas" not in pool


def test_no_template_enables_sms_or_email_codes_or_a_feature_plan():
    templates = [
        *TEMPLATES.values(),
        PROD_APP_TEMPLATE,
        *(template for pair in SYNTHS.values() for template in pair),
    ]
    for template in templates:
        rendered = json.dumps(template)
        for forbidden in ("SmsConfiguration", "SMS_MFA", "EMAIL_OTP", "UserPoolTier"):
            assert forbidden not in rendered
        # An SMS role is a role Cognito itself assumes.
        assert '"cognito-idp.amazonaws.com"' not in rendered


def test_managed_page_brands_every_domain_from_the_committed_files():
    template = SYNTHS["app-managed-domain"][0]
    domains = _domains(template)
    assert len(domains) == 2
    assert all(domain["ManagedLoginVersion"] == 2 for domain in domains)
    [(_, branding)] = _resources(template, "AWS::Cognito::ManagedLoginBranding")
    properties = branding["Properties"]
    [(client_id, _)] = _resources(template, "AWS::Cognito::UserPoolClient")
    assert properties["ClientId"] == {"Ref": client_id}
    assert properties["Settings"] == json.loads((BRANDING / "settings.json").read_text())
    assert properties["Assets"] == [
        {
            "Category": asset["category"],
            "ColorMode": asset["color_mode"],
            "Extension": asset["extension"],
            "Bytes": base64.b64encode((BRANDING / asset["file"]).read_bytes()).decode(),
        }
        for asset in json.loads((BRANDING / "assets.json").read_text())
    ]


@pytest.mark.parametrize("name", ["app-classic", "off-classic"])
def test_classic_page_names_version_1_on_every_domain_and_has_no_branding(name):
    template = SYNTHS[name][0]
    assert [domain["ManagedLoginVersion"] for domain in _domains(template)] == [1]
    assert not _resources(template, "AWS::Cognito::ManagedLoginBranding")


def test_domain_adds_custom_domain_certificate_alias_record_and_csp_sources():
    app_template, cert_template = SYNTHS["app-managed-domain"]
    [(certificate_id, certificate)] = [
        (logical_id, resource)
        for logical_id, resource in _resources(cert_template, "AWS::CertificateManager::Certificate")
        if resource["Properties"]["DomainName"] == AUTH_DOMAIN
    ]
    assert certificate["Properties"]["ValidationMethod"] == "DNS"
    [custom] = [domain for domain in _domains(app_template) if "CustomDomainConfig" in domain]
    assert custom["Domain"] == AUTH_DOMAIN
    assert certificate_id in json.dumps(custom["CustomDomainConfig"]["CertificateArn"])
    [record] = [
        resource["Properties"]
        for _, resource in _resources(app_template, "AWS::Route53::RecordSet")
        if resource["Properties"]["Name"] == f"{AUTH_DOMAIN}."
    ]
    assert record["Type"] == "A"
    # cdk.json's flag: the record names the custom domain's own CloudFront address.
    [custom_id] = [
        logical_id
        for logical_id, resource in _resources(app_template, "AWS::Cognito::UserPoolDomain")
        if "CustomDomainConfig" in resource["Properties"]
    ]
    assert record["AliasTarget"]["DNSName"] == {"Fn::GetAtt": [custom_id, "CloudFrontDistribution"]}
    assert not _resources(app_template, "Custom::UserPoolCloudFrontDomainName")
    lambdas = {logical_id for logical_id, _ in _resources(app_template, "AWS::Lambda::Function")}
    no_domain_lambdas = {
        logical_id for logical_id, _ in _resources(SYNTHS["app-classic"][0], "AWS::Lambda::Function")
    }
    assert lambdas == no_domain_lambdas
    directives = _csp_directives(app_template)
    prefix = "https://policy-atlas-v3.auth.eu-west-2.amazoncognito.com"
    for directive in ("connect-src", "frame-src"):
        sources = directives[directive].split()
        assert prefix in sources and f"https://{AUTH_DOMAIN}" in sources


def test_rollback_to_classic_page_keeps_the_domain_on_version_1_without_branding():
    template = SYNTHS["app-classic-domain"][0]
    assert [domain["ManagedLoginVersion"] for domain in _domains(template)] == [1, 1]
    assert not _resources(template, "AWS::Cognito::ManagedLoginBranding")


def test_no_domain_adds_no_custom_domain_certificate_record_or_csp_source():
    app_template, cert_template = SYNTHS["app-classic"]
    assert all("CustomDomainConfig" not in domain for domain in _domains(app_template))
    assert len(_resources(cert_template, "AWS::CertificateManager::Certificate")) == 1
    assert AUTH_DOMAIN not in json.dumps(app_template)


@pytest.mark.parametrize("sign_in", [
    {"sms": "off"},
    {"mfa": "email"},
    {"mfa": "App"},
    {"page": "custom"},
    {"domain": "login.v3.policyatlas.uk"},
    {"domain": "auth.policyatlas.uk"},
])
def test_unknown_key_value_or_domain_fails_synth(sign_in):
    with pytest.raises(ValueError, match="sign_in"):
        CognitoAuth(
            cdk.Stack(cdk.App(), "SignInStack"),
            "CognitoAuth",
            domain_name="v3.policyatlas.uk",
            domain_prefix="policy-atlas-v3",
            sign_in=sign_in,
        )


@pytest.mark.parametrize("sign_in", [False, [], "x"])
def test_sign_in_that_is_not_a_mapping_fails_synth(sign_in):
    with pytest.raises(ValueError, match="sign_in"):
        CognitoAuth(
            cdk.Stack(cdk.App(), "SignInStack"),
            "CognitoAuth",
            domain_name="v3.policyatlas.uk",
            domain_prefix="policy-atlas-v3",
            sign_in=sign_in,
        )
    with pytest.raises(ValueError, match="sign_in"):
        sign_in_block(sign_in)


def test_null_sign_in_equals_an_absent_block():
    assert sign_in_block(None) == {}
    stacks = []
    for sign_in in (None, {}):
        stack = cdk.Stack(cdk.App(), "SignInStack")
        CognitoAuth(
            stack,
            "CognitoAuth",
            domain_name="v3.policyatlas.uk",
            domain_prefix="policy-atlas-v3",
            sign_in=sign_in,
        )
        stacks.append(Template.from_stack(stack).to_json())
    assert stacks[0] == stacks[1]


def test_domain_without_certificate_fails_synth():
    with pytest.raises(ValueError, match="auth_certificate"):
        CognitoAuth(
            cdk.Stack(cdk.App(), "SignInStack"),
            "CognitoAuth",
            domain_name="v3.policyatlas.uk",
            domain_prefix="policy-atlas-v3",
            sign_in={"domain": AUTH_DOMAIN},
        )
