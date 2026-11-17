"""The firewall in front of the public API.

In plain words, AWS WAF (Web Application Firewall) checks a web request before
the load balancer sends it to the API.  A web ACL is the firewall's list of
rules.  A scope-down statement narrows a rule to a host or path.  Rate-based
rules count requests from an address over a time window; managed rule groups
are AWS-maintained attack-detection rules.  Count mode records matches without
refusing them, while CAPTCHA asks a visitor to solve a puzzle.  The token domain
is the site domain for which WAF can issue that CAPTCHA token.
"""

from aws_cdk import ArnFormat, RemovalPolicy, Stack, aws_logs as logs, aws_wafv2 as wafv2
from constructs import Construct

# Pinned by the Phase 0 measurement; never below 3,000.
GENERAL_RATE_LIMIT = 3000
WAITLIST_RATE_LIMIT = 50
RATE_WINDOW_SECONDS = 300
CAPTCHA_IMMUNITY_SECONDS = 1800
COMMON_RULES_ALWAYS_COUNTED = ("SizeRestrictions_BODY",)
WEB_ACL_NAME = "policy-atlas-v3-api"
LOG_GROUP_NAME = "aws-waf-logs-policy-atlas-v3"
WAF_MODES = ("count", "block")
HEALTH_PATHS = ("/healthz", "/readyz")
WAITLIST_PATH = "/api/v1/waitlist"


def _transform(priority: int, kind: str) -> wafv2.CfnWebACL.TextTransformationProperty:
    return wafv2.CfnWebACL.TextTransformationProperty(priority=priority, type=kind)


def _byte_match(
    *, field: wafv2.CfnWebACL.FieldToMatchProperty, constraint: str,
    search: str, transformations: list[wafv2.CfnWebACL.TextTransformationProperty],
) -> wafv2.CfnWebACL.StatementProperty:
    return wafv2.CfnWebACL.StatementProperty(
        byte_match_statement=wafv2.CfnWebACL.ByteMatchStatementProperty(
            field_to_match=field,
            positional_constraint=constraint,
            search_string=search,
            text_transformations=transformations,
        )
    )


def _api_host(api_host: str) -> wafv2.CfnWebACL.StatementProperty:
    return _byte_match(
        field=wafv2.CfnWebACL.FieldToMatchProperty(
            single_header=wafv2.CfnWebACL.SingleHeaderProperty(name="host")
        ),
        constraint="EXACTLY",
        search=api_host,
        transformations=[_transform(0, "LOWERCASE")],
    )


def _not_health() -> wafv2.CfnWebACL.StatementProperty:
    paths = [
        _byte_match(
            field=wafv2.CfnWebACL.FieldToMatchProperty(uri_path={}),
            constraint="STARTS_WITH",
            search=path,
            transformations=[_transform(0, "NONE")],
        )
        for path in HEALTH_PATHS
    ]
    return wafv2.CfnWebACL.StatementProperty(
        not_statement=wafv2.CfnWebACL.NotStatementProperty(
            statement=wafv2.CfnWebACL.StatementProperty(
                or_statement=wafv2.CfnWebACL.OrStatementProperty(statements=paths)
            )
        )
    )


def _waitlist_post() -> wafv2.CfnWebACL.StatementProperty:
    path = _byte_match(
        field=wafv2.CfnWebACL.FieldToMatchProperty(uri_path={}),
        constraint="EXACTLY",
        search=WAITLIST_PATH,
        transformations=[_transform(0, "URL_DECODE"), _transform(1, "LOWERCASE")],
    )
    method = _byte_match(
        field=wafv2.CfnWebACL.FieldToMatchProperty(method={}),
        constraint="EXACTLY",
        search="POST",
        transformations=[_transform(0, "NONE")],
    )
    return wafv2.CfnWebACL.StatementProperty(
        and_statement=wafv2.CfnWebACL.AndStatementProperty(statements=[path, method])
    )


def _visibility(name: str) -> wafv2.CfnWebACL.VisibilityConfigProperty:
    return wafv2.CfnWebACL.VisibilityConfigProperty(
        cloud_watch_metrics_enabled=True,
        sampled_requests_enabled=True,
        metric_name=name,
    )


class ApiFirewall(Construct):
    """A regional WAF web ACL, its load-balancer association and matched-request log."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        load_balancer_arn: str,
        api_host: str,
        domain_name: str,
        waf_config: dict,
    ) -> None:
        super().__init__(scope, id)
        self.web_acl: wafv2.CfnWebACL | None = None

        if not isinstance(waf_config, dict):
            raise ValueError("backend.waf must be a dict in pa_config.json.")
        required = {"enabled", "mode", "captcha"}
        if set(waf_config) != required:
            missing = required - set(waf_config)
            unexpected = set(waf_config) - required
            if missing:
                raise ValueError(f"backend.waf.{sorted(missing)[0]} is required in pa_config.json.")
            raise ValueError(f"backend.waf.{sorted(unexpected)[0]} is not a known key in pa_config.json.")
        enabled = waf_config["enabled"]
        mode = waf_config["mode"]
        captcha = waf_config["captcha"]
        if type(enabled) is not bool:
            raise ValueError("backend.waf.enabled must be a bool in pa_config.json.")
        if mode not in WAF_MODES:
            raise ValueError(
                f"backend.waf.mode must be one of {WAF_MODES} in pa_config.json, got {mode!r}."
            )
        if type(captcha) is not bool:
            raise ValueError("backend.waf.captcha must be a bool in pa_config.json.")
        if captcha and not enabled:
            raise ValueError("backend.waf.captcha requires backend.waf.enabled in pa_config.json.")
        if not enabled:
            return

        rules = self._rules(api_host=api_host, mode=mode, captcha=captcha)
        acl = wafv2.CfnWebACL(
            self,
            "WebAcl",
            scope="REGIONAL",
            name=WEB_ACL_NAME,
            default_action={"allow": {}},
            visibility_config=_visibility("pa-v3-waf"),
            token_domains=[domain_name] if captcha else None,
            rules=rules,
        )
        self.web_acl = acl
        wafv2.CfnWebACLAssociation(
            self,
            "WebAclAssociation",
            resource_arn=load_balancer_arn,
            web_acl_arn=acl.attr_arn,
        )
        group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=LOG_GROUP_NAME,
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        logging = wafv2.CfnLoggingConfiguration(
            self,
            "Logging",
            resource_arn=acl.attr_arn,
            log_destination_configs=[
                Stack.of(self).format_arn(
                    service="logs",
                    resource="log-group",
                    resource_name=LOG_GROUP_NAME,
                    arn_format=ArnFormat.COLON_RESOURCE_NAME,
                )
            ],
            logging_filter=wafv2.CfnLoggingConfiguration.LoggingFilterProperty(
                default_behavior="DROP",
                filters=[wafv2.CfnLoggingConfiguration.FilterProperty(
                    behavior="KEEP",
                    requirement="MEETS_ANY",
                    conditions=[wafv2.CfnLoggingConfiguration.ConditionProperty(
                        action_condition=wafv2.CfnLoggingConfiguration.ActionConditionProperty(action=action)
                    ) for action in ("COUNT", "BLOCK", "CAPTCHA", "EXCLUDED_AS_COUNT")],
                )],
            ),
        )
        logging.node.add_dependency(group)

    def _rules(self, *, api_host: str, mode: str, captcha: bool) -> list[wafv2.CfnWebACL.RuleProperty]:
        rules: list[wafv2.CfnWebACL.RuleProperty] = []
        if captcha:
            rules.append(wafv2.CfnWebACL.RuleProperty(
                name="waitlist-captcha",
                priority=10,
                statement=_waitlist_post(),
                action={"captcha": {}},
                captcha_config=wafv2.CfnWebACL.CaptchaConfigProperty(
                    immunity_time_property=wafv2.CfnWebACL.ImmunityTimePropertyProperty(
                        immunity_time=CAPTCHA_IMMUNITY_SECONDS
                    )
                ),
                visibility_config=_visibility("waitlist-captcha"),
            ))
        rules.extend([
            wafv2.CfnWebACL.RuleProperty(
                name="waitlist-rate",
                priority=20,
                statement=wafv2.CfnWebACL.StatementProperty(
                    rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                        aggregate_key_type="IP",
                        limit=WAITLIST_RATE_LIMIT,
                        evaluation_window_sec=RATE_WINDOW_SECONDS,
                        scope_down_statement=_waitlist_post(),
                    )
                ),
                action={"block": {}},
                visibility_config=_visibility("waitlist-rate"),
            ),
            wafv2.CfnWebACL.RuleProperty(
                name="general-rate",
                priority=30,
                statement=wafv2.CfnWebACL.StatementProperty(
                    rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                        aggregate_key_type="IP",
                        limit=GENERAL_RATE_LIMIT,
                        evaluation_window_sec=RATE_WINDOW_SECONDS,
                        scope_down_statement=_api_host(api_host),
                    )
                ),
                action={"block": {}} if mode == "block" else {"count": {}},
                visibility_config=_visibility("general-rate"),
            ),
        ])
        managed_groups = (
            ("managed-common", 40, "AWSManagedRulesCommonRuleSet"),
            ("managed-known-bad-inputs", 50, "AWSManagedRulesKnownBadInputsRuleSet"),
            ("managed-ip-reputation", 60, "AWSManagedRulesAmazonIpReputationList"),
        )
        for rule_name, priority, group_name in managed_groups:
            kwargs = {}
            if rule_name == "managed-common":
                kwargs["rule_action_overrides"] = [
                    wafv2.CfnWebACL.RuleActionOverrideProperty(
                        name=name, action_to_use={"count": {}}
                    )
                    for name in COMMON_RULES_ALWAYS_COUNTED
                ]
            rules.append(wafv2.CfnWebACL.RuleProperty(
                name=rule_name,
                priority=priority,
                statement=wafv2.CfnWebACL.StatementProperty(
                    managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                        name=group_name,
                        vendor_name="AWS",
                        scope_down_statement=wafv2.CfnWebACL.StatementProperty(
                            and_statement=wafv2.CfnWebACL.AndStatementProperty(
                                statements=[_api_host(api_host), _not_health()]
                            )
                        ),
                        **kwargs,
                    )
                ),
                override_action={"none": {}} if mode == "block" else {"count": {}},
                visibility_config=_visibility(rule_name),
            ))
        return rules
