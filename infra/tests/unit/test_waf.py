"""Rendered-template checks for the API firewall."""
import json

import aws_cdk as cdk
import pytest
from aws_cdk import Environment
from aws_cdk.assertions import Template

from infra.components import waf
from infra.components.waf import ApiFirewall
from tests.unit.test_synth import INFRA_ROOT, TEMPLATES, _resources

APP = TEMPLATES["app"]
ALB_ARN = "arn:aws:elasticloadbalancing:eu-west-2:111111111111:loadbalancer/app/pa-v3-alb/abc"


def _configs() -> dict:
    return json.loads((INFRA_ROOT / "pa_config.json").read_text())


HOSTS = ["api.v3.policyatlas.uk", "ops.v3.policyatlas.uk", "metabase.v3.policyatlas.uk"]


def _host_statement(hosts: list[str] = HOSTS) -> dict:
    matches = [{"ByteMatchStatement": {
        "FieldToMatch": {"SingleHeader": {"Name": "host"}},
        "PositionalConstraint": "STARTS_WITH", "SearchString": host,
        "TextTransformations": [{"Priority": 0, "Type": "LOWERCASE"}],
    }} for host in hosts]
    return matches[0] if len(matches) == 1 else {"OrStatement": {"Statements": matches}}


def _synth(config: dict, *, hosts: list[str] = HOSTS,
           domain_name: str = "v3.policyatlas.uk") -> dict:
    app = cdk.App()
    stack = cdk.Stack(app, "WafStack", env=Environment(account="111111111111", region="eu-west-2"))
    ApiFirewall(stack, "Firewall", load_balancer_arn=ALB_ARN, hosts=hosts,
                domain_name=domain_name, waf_config=config)
    return Template.from_stack(stack).to_json()


def _one(template: dict, resource_type: str) -> tuple[str, dict]:
    matches = _resources(template, resource_type)
    assert len(matches) == 1
    return matches[0]


def _acl(template: dict) -> tuple[str, dict]:
    return _one(template, "AWS::WAFv2::WebACL")


def _keys(obj):
    """Every dict key anywhere inside ``obj``."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _keys(item)


def _rule(template: dict, name: str) -> dict:
    _, acl = _acl(template)
    return next(rule for rule in acl["Properties"]["Rules"] if rule["Name"] == name)


def _assert_visibility(visibility: dict, name: str) -> None:
    assert visibility == {
        "CloudWatchMetricsEnabled": True,
        "SampledRequestsEnabled": True,
        "MetricName": name,
    }


def _waitlist_statement() -> dict:
    return {
        "AndStatement": {"Statements": [
            {"ByteMatchStatement": {
                "FieldToMatch": {"UriPath": {}}, "PositionalConstraint": "EXACTLY",
                "SearchString": waf.WAITLIST_PATH,
                "TextTransformations": [{"Priority": 0, "Type": "URL_DECODE"},
                                        {"Priority": 1, "Type": "LOWERCASE"}],
            }},
            {"ByteMatchStatement": {
                "FieldToMatch": {"Method": {}}, "PositionalConstraint": "EXACTLY",
                "SearchString": "POST", "TextTransformations": [{"Priority": 0, "Type": "NONE"}],
            }},
        ]}
    }


def test_w1_web_acl_association_config_pin_and_validation():
    configs = _configs()
    staging = configs["staging"]["policy_atlas_config"]["backend"]["waf"]
    prod = configs["prod"]["policy_atlas_config"]["backend"]["waf"]
    assert staging == {"enabled": True, "mode": "count", "captcha": True}
    assert prod == {"enabled": True, "mode": "count", "captcha": False}

    acl_id, acl = _acl(APP)
    properties = acl["Properties"]
    assert properties["Scope"] == "REGIONAL"
    assert properties["Name"] == waf.WEB_ACL_NAME
    assert properties["DefaultAction"] == {"Allow": {}}
    _assert_visibility(properties["VisibilityConfig"], waf.WEB_ACL_NAME)
    _, association = _one(APP, "AWS::WAFv2::WebACLAssociation")
    assert association["Properties"]["WebACLArn"] == {"Fn::GetAtt": [acl_id, "Arn"]}
    parameter = next(
        name for name, value in APP["Parameters"].items()
        if value.get("Default") == "/policy_atlas_v3/shared_alb/arn"
    )
    assert association["Properties"]["ResourceArn"] == {"Ref": parameter}
    assert len(_resources(_synth(prod), "AWS::WAFv2::WebACL")) == 1
    assert len(_resources(_synth(prod), "AWS::WAFv2::WebACLAssociation")) == 1

    disabled = _synth({"enabled": False, "mode": "count", "captcha": False})
    assert not [resource for resource in disabled.get("Resources", {}).values()
                if resource["Type"].startswith("AWS::WAFv2::")]
    assert not [resource for resource in disabled.get("Resources", {}).values()
                if resource["Type"] == "AWS::Logs::LogGroup"]
    invalid = [
        {"enabled": True, "mode": "count"},
        {"enabled": True, "mode": "audit", "captcha": False},
        {"enabled": "true", "mode": "count", "captcha": False},
        {"enabled": False, "mode": "count", "captcha": True},
        None,
    ]
    for config in invalid:
        with pytest.raises(ValueError):
            _synth(config)


def test_w2_waitlist_rate_rule_is_always_blocking_and_decodes_the_path():
    for mode in waf.WAF_MODES:
        rule = _rule(_synth({"enabled": True, "mode": mode, "captcha": False}), "waitlist-rate")
        rate = rule["Statement"]["RateBasedStatement"]
        assert rate["Limit"] == waf.WAITLIST_RATE_LIMIT
        assert rate["EvaluationWindowSec"] == waf.RATE_WINDOW_SECONDS
        assert rate["AggregateKeyType"] == "IP"
        assert rate["ScopeDownStatement"] == _waitlist_statement()
        assert rule["Action"] == {"Block": {}}


def test_w3_general_rate_rule_is_host_scoped_and_mode_controlled():
    assert waf.GENERAL_RATE_LIMIT >= 3000
    for mode, action in (("count", {"Count": {}}), ("block", {"Block": {}})):
        rule = _rule(_synth({"enabled": True, "mode": mode, "captcha": False}), "general-rate")
        rate = rule["Statement"]["RateBasedStatement"]
        assert rate["Limit"] == waf.GENERAL_RATE_LIMIT
        assert rate["ScopeDownStatement"] == _host_statement()
        assert rule["Action"] == action


def test_w4_managed_rules_are_host_scoped_skip_health_and_keep_body_counted():
    expected = {
        "managed-common": (40, "AWSManagedRulesCommonRuleSet"),
        "managed-known-bad-inputs": (50, "AWSManagedRulesKnownBadInputsRuleSet"),
        "managed-ip-reputation": (60, "AWSManagedRulesAmazonIpReputationList"),
    }
    for mode, override in (("count", {"Count": {}}), ("block", {"None": {}})):
        template = _synth({"enabled": True, "mode": mode, "captcha": False})
        for name, (priority, group_name) in expected.items():
            rule = _rule(template, name)
            assert rule["Priority"] == priority
            assert rule["OverrideAction"] == override
            assert "Action" not in rule
            group = rule["Statement"]["ManagedRuleGroupStatement"]
            assert group["VendorName"] == "AWS" and group["Name"] == group_name
            statements = group["ScopeDownStatement"]["AndStatement"]["Statements"]
            assert statements[0] == _host_statement()
            paths = statements[1]["NotStatement"]["Statement"]["OrStatement"]["Statements"]
            assert [item["ByteMatchStatement"]["SearchString"] for item in paths] == list(waf.HEALTH_PATHS)
            assert all(item["ByteMatchStatement"]["PositionalConstraint"] == "EXACTLY" for item in paths)
            assert all(item["ByteMatchStatement"]["FieldToMatch"] == {"UriPath": {}} for item in paths)
            assert all(item["ByteMatchStatement"]["TextTransformations"] == [{"Priority": 0, "Type": "NONE"}]
                       for item in paths)
            if name == "managed-common":
                assert group["RuleActionOverrides"] == [{"Name": "SizeRestrictions_BODY", "ActionToUse": {"Count": {}}}]
            else:
                assert "RuleActionOverrides" not in group


def test_w5_captcha_rule_precedes_rate_rule_and_controls_token_domains():
    prod = _configs()["prod"]["policy_atlas_config"]["backend"]["waf"]
    for config in (prod, {"enabled": True, "mode": "count", "captcha": False}):
        _, acl = _acl(_synth(config))
        assert "TokenDomains" not in acl["Properties"]
        assert all(rule["Name"] != "waitlist-captcha" for rule in acl["Properties"]["Rules"])
    for domain in ("v3.policyatlas.uk", "policyatlas.uk"):
        template = _synth({"enabled": True, "mode": "count", "captcha": True}, domain_name=domain)
        _, acl = _acl(template)
        captcha = _rule(template, "waitlist-captcha")
        rate = _rule(template, "waitlist-rate")
        assert captcha["Priority"] < rate["Priority"]
        assert captcha["Statement"] == rate["Statement"]["RateBasedStatement"]["ScopeDownStatement"] == _waitlist_statement()
        assert captcha["Action"] == {"Captcha": {}}
        assert captcha["CaptchaConfig"]["ImmunityTimeProperty"]["ImmunityTime"] == waf.CAPTCHA_IMMUNITY_SECONDS
        assert acl["Properties"]["TokenDomains"] == [domain]


def test_w8_logging_and_visibility_configs_are_rendered_for_matches_only():
    acl_id, acl = _acl(APP)
    log_id, log_group = next(
        item for item in _resources(APP, "AWS::Logs::LogGroup")
        if item[1]["Properties"]["LogGroupName"] == waf.LOG_GROUP_NAME
    )
    assert log_group["Properties"]["RetentionInDays"] == 30
    assert log_group["DeletionPolicy"] == "Delete"
    _, logging = _one(APP, "AWS::WAFv2::LoggingConfiguration")
    properties = logging["Properties"]
    assert properties["ResourceArn"] == {"Fn::GetAtt": [acl_id, "Arn"]}
    assert len(properties["LogDestinationConfigs"]) == 1
    destination = properties["LogDestinationConfigs"][0]
    assert "aws-waf-logs-policy-atlas-v3" in json.dumps(destination)
    assert ":*" not in json.dumps(destination)
    # CloudFormation's key names (PascalCase); CDK types this property `Any`.
    log_filter = properties["LoggingFilter"]
    assert log_filter["DefaultBehavior"] == "DROP"
    (filter_,) = log_filter["Filters"]
    assert (filter_["Behavior"], filter_["Requirement"]) == ("KEEP", "MEETS_ANY")
    assert {condition["ActionCondition"]["Action"] for condition in filter_["Conditions"]} == {
        "COUNT", "BLOCK", "CAPTCHA", "EXCLUDED_AS_COUNT"
    }
    assert not any(key[0].islower() for key in json.dumps(log_filter).split('"')[1::2] if key)
    assert log_id in logging["DependsOn"]
    # The bearer token of a counted signed-in request must never reach the log.
    assert properties["RedactedFields"] == [
        {"SingleHeader": {"Name": name}} for name in ("authorization", "cookie", "x-aws-waf-token")
    ]
    _assert_visibility(acl["Properties"]["VisibilityConfig"], waf.WEB_ACL_NAME)
    for rule in acl["Properties"]["Rules"]:
        _assert_visibility(rule["VisibilityConfig"], rule["Name"])
    # Every Any-typed field (SingleHeader, UriPath, …) must render CloudFormation's
    # PascalCase keys; `aws wafv2 check-capacity` rejected a lower-case "name" (2026-11-18).
    assert not [key for key in _keys(acl["Properties"]) if key[0].islower()]


def test_one_host_renders_without_an_or_statement_and_no_host_is_refused():
    config = {"enabled": True, "mode": "count", "captcha": False}
    rule = _rule(_synth(config, hosts=HOSTS[:1]), "general-rate")
    assert rule["Statement"]["RateBasedStatement"]["ScopeDownStatement"] == _host_statement(HOSTS[:1])
    with pytest.raises(ValueError, match="at least one host"):
        _synth(config, hosts=[])
