"""Rendered-template checks for task 064d's sign-in settings (ADR 0049)."""
import json
import os

from tests.unit.test_synth import INFRA_ROOT, PROD_APP_TEMPLATE, TEMPLATES, _resources

BASELINE = INFRA_ROOT / "tests" / "unit" / "fixtures" / "sign_in_all_off.json"
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


def test_m6_production_sign_in_resources_equal_baseline():
    # With no `sign_in` block the change adds nothing. Regenerate the baseline only from
    # code that predates the change: UPDATE_SIGN_IN_BASELINE=1 make -C infra test.
    rendered = _sign_in_resources(PROD_APP_TEMPLATE, TEMPLATES["cert"])
    if os.environ.get("UPDATE_SIGN_IN_BASELINE") == "1":
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(rendered, indent=1, sort_keys=True) + "\n")
    assert rendered == json.loads(BASELINE.read_text())
