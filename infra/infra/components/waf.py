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

# Pinned by the measurement (2026-11-17): the busiest 5-minute window in 14 days
# of the staging API log held 520 non-health requests from all clients together, so no
# single address sent more; ten times that, rounded up to a thousand. Never below 3,000.
GENERAL_RATE_LIMIT = 6000
WAITLIST_RATE_LIMIT = 50
RATE_WINDOW_SECONDS = 300
CAPTCHA_IMMUNITY_SECONDS = 1800
COMMON_RULES_ALWAYS_COUNTED = ("SizeRestrictions_BODY",)
WEB_ACL_NAME = "policy-atlas-v3-api"
LOG_GROUP_NAME = "aws-waf-logs-policy-atlas-v3"
WAF_MODES = ("count", "block")
HEALTH_PATHS = ("/healthz", "/readyz")
WAITLIST_PATH = "/api/v1/waitlist"


def _byte_match(
    *, field: wafv2.CfnWebACL.FieldToMatchProperty, constraint: str,
    search: str, transforms: tuple[str, ...] = ("NONE",),
) -> wafv2.CfnWebACL.StatementProperty:
    """One byte-match statement; ``transforms`` are applied in the order given."""
    return wafv2.CfnWebACL.StatementProperty(
        byte_match_statement=wafv2.CfnWebACL.ByteMatchStatementProperty(
            field_to_match=field,
            positional_constraint=constraint,
            search_string=search,
            text_transformations=[
                wafv2.CfnWebACL.TextTransformationProperty(priority=i, type=kind)
                for i, kind in enumerate(transforms)
            ],
        )
    )


def _api_host(api_host: str) -> wafv2.CfnWebACL.StatementProperty:
    # STARTS_WITH, not EXACTLY: the load balancer routes on the host name and
    # ignores a ":443" suffix or a trailing dot, so a request that reaches the
    # API may carry either; an exact match would let it skip these rules.
    return _byte_match(
        # single_header is typed Any: a SingleHeaderProperty would render "name",
        # which the WAF service rejects (docs/knowledge/cdk-any-typed-property-…).
        field=wafv2.CfnWebACL.FieldToMatchProperty(single_header={"Name": "host"}),
        constraint="STARTS_WITH",
        search=api_host,
        transforms=("LOWERCASE",),
    )


def _not_health() -> wafv2.CfnWebACL.StatementProperty:
    paths = [
        _byte_match(
            field=wafv2.CfnWebACL.FieldToMatchProperty(uri_path={}),
            constraint="EXACTLY",
            search=path,
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
        transforms=("URL_DECODE", "LOWERCASE"),
    )
    method = _byte_match(
        field=wafv2.CfnWebACL.FieldToMatchProperty(method={}),
        constraint="EXACTLY",
        search="POST",
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


def _rate_rule(
    name: str, priority: int, limit: int,
    scope_down: wafv2.CfnWebACL.StatementProperty, *, action: dict,
) -> wafv2.CfnWebACL.RuleProperty:
    """A rate-based rule: ``limit`` requests per address per window over ``scope_down``."""
    return wafv2.CfnWebACL.RuleProperty(
        name=name,
        priority=priority,
        statement=wafv2.CfnWebACL.StatementProperty(
            rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                aggregate_key_type="IP",
                limit=limit,
                evaluation_window_sec=RATE_WINDOW_SECONDS,
                scope_down_statement=scope_down,
            )
        ),
        action=action,
        visibility_config=_visibility(name),
    )


# Request headers the firewall log never stores. A counted request is logged
# with every header, so without this a signed-in person's bearer token would
# sit in the log group for a month.
REDACTED_HEADERS = ("authorization", "cookie", "x-aws-waf-token")


class ApiFirewall(Construct):
    """A regional WAF web ACL, its load-balancer association and matched-request log.

    Args:
        scope: The parent construct (the app stack).
        id: The construct id.
        load_balancer_arn: The shared load balancer's ARN (an SSM-resolved token).
        api_host: The API's host name, ``api.<domain_name>``; the general rate rule
            and the managed groups match only requests whose Host header starts
            with it.
        domain_name: The environment's domain; the one entry in the token domain
            list when the CAPTCHA is on, so a token issued on the splash page is
            accepted on the API's host.
        waf_config: The ``backend.waf`` object from ``pa_config.json``, exactly the
            keys ``enabled`` (bool), ``mode`` (``"count"`` or ``"block"``) and
            ``captcha`` (bool). ``enabled: false`` creates nothing.

    Raises:
        ValueError: A key is missing or unknown, a value has the wrong type or is
            not one of the allowed values, or ``captcha`` is true with ``enabled``
            false. Raised even when ``enabled`` is false, so every environment's
            config is checked at synth.

    Attributes:
        web_acl: The ``CfnWebACL``, or ``None`` when the firewall is off.
    """

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
            # The metric name is the ACL name: CloudWatch's WebACL dimension takes
            # the metric name, and the report script queries by the ACL name.
            visibility_config=_visibility(WEB_ACL_NAME),
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
            redacted_fields=[
                wafv2.CfnLoggingConfiguration.FieldToMatchProperty(single_header={"Name": name})
                for name in REDACTED_HEADERS
            ],
            # A plain dict with CloudFormation's own key names: this property is
            # typed `Any` in CDK 2.261, so a typed LoggingFilterProperty is
            # serialised camelCase and CloudFormation rejects it.
            logging_filter={
                "DefaultBehavior": "DROP",
                "Filters": [{
                    "Behavior": "KEEP",
                    "Requirement": "MEETS_ANY",
                    "Conditions": [
                        {"ActionCondition": {"Action": action}}
                        for action in ("COUNT", "BLOCK", "CAPTCHA", "EXCLUDED_AS_COUNT")
                    ],
                }],
            },
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
        rules.append(_rate_rule(
            "waitlist-rate", 20, WAITLIST_RATE_LIMIT, _waitlist_post(), action={"block": {}}
        ))
        rules.append(_rate_rule(
            "general-rate", 30, GENERAL_RATE_LIMIT, _api_host(api_host),
            action={"block": {}} if mode == "block" else {"count": {}},
        ))
        # (rule name, priority, AWS group name, rules inside it always counted)
        managed_groups = (
            ("managed-common", 40, "AWSManagedRulesCommonRuleSet", COMMON_RULES_ALWAYS_COUNTED),
            ("managed-known-bad-inputs", 50, "AWSManagedRulesKnownBadInputsRuleSet", ()),
            ("managed-ip-reputation", 60, "AWSManagedRulesAmazonIpReputationList", ()),
        )
        for rule_name, priority, group_name, always_counted in managed_groups:
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
                        rule_action_overrides=[
                            wafv2.CfnWebACL.RuleActionOverrideProperty(name=name, action_to_use={"count": {}})
                            for name in always_counted
                        ] or None,
                    )
                ),
                override_action={"none": {}} if mode == "block" else {"count": {}},
                visibility_config=_visibility(rule_name),
            ))
        return rules
