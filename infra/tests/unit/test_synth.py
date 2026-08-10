"""Synthesized-template assertions for task 026 infrastructure resources.

The stacks are synthesized once at module import.  The harness deliberately
disables CDK bundling and substitutes the pending backend image asset so these
tests require neither AWS credentials nor a Docker daemon.
"""
import json
import os
from pathlib import Path
from unittest.mock import patch

import aws_cdk as cdk
from aws_cdk import Environment, aws_ecs as ecs
from aws_cdk.assertions import Template

from infra.database_stack import DatabaseStack
from infra.cert_stack import PaV3CertStack
from infra.network_stack import NetworkStack
from infra.policy_atlas_stack import PolicyAtlasStack

INFRA_ROOT = Path(__file__).resolve().parents[2]
DUMMY_ACCOUNT = "111111111111"
ENV_NAME = "staging"
VPC_NAME = "policy-atlas-v3-vpc-staging"
SSM_PREFIX = "/policy_atlas_v3/"

# Mirrors port-map.md's namespacing table for the stacks implemented so far.
NAMESPACING_CASES = (
    ("VPC name", VPC_NAME, ("network",)),
    ("ALB", "pa-v3-alb", ("network",)),
    ("Target group", "pa-v3-api-tg", ("app",)),
    ("Aurora cluster id", "policy-atlas-v3-db-cluster", ("database",)),
    ("Aurora writer instance id", "policy-atlas-v3-db-writer", ("database",)),
    ("ECS cluster", "policy-atlas-v3-cluster", ("app",)),
    ("ECS service", "policy-atlas-v3-api-service", ("app",)),
    ("API task family", "policy-atlas-v3-api", ("app",)),
    ("Log group", "/policy_atlas_v3/application", ("app",)),
    ("Domain", "v3.policyatlas.uk", ("network", "app")),
    ("Hosted UI prefix", "policy-atlas-v3", ("app",)),
)


def _load_config(filename: str) -> dict:
    with open(INFRA_ROOT / filename) as config_file:
        return json.load(config_file)[ENV_NAME]


def _resources(template: dict, resource_type: str) -> list[tuple[str, dict]]:
    return [
        (logical_id, resource)
        for logical_id, resource in template["Resources"].items()
        if resource["Type"] == resource_type
    ]


def _port_5432_ingress(template: dict) -> list[dict]:
    return [
        resource["Properties"]
        for _, resource in _resources(template, "AWS::EC2::SecurityGroupIngress")
        if resource["Properties"].get("FromPort") == 5432
        and resource["Properties"].get("ToPort") == 5432
    ]


# Keep this setup at module scope: CDK synth is expensive and all tests below
# reuse the same immutable template dictionaries.
os.environ["CDK_DEFAULT_ACCOUNT"] = DUMMY_ACCOUNT
os.environ["JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION"] = "1"
NETWORK_CONFIG = _load_config("network_config.json")
DB_CONFIG = _load_config("db_config.json")
PA_CONFIG = _load_config("pa_config.json")
APP = cdk.App(context={"aws:cdk:bundling-stacks": []})
ENV = Environment(account=DUMMY_ACCOUNT, region=NETWORK_CONFIG["aws_region"])
CERT_ENV = Environment(account=DUMMY_ACCOUNT, region="us-east-1")
NETWORK_STACK = NetworkStack(
    APP,
    "PaV3NetworkStack",
    network_config=NETWORK_CONFIG,
    env=ENV,
    aws_region=NETWORK_CONFIG["aws_region"],
    env_name=ENV_NAME,
)
DATABASE_STACK = DatabaseStack(
    APP,
    "PaV3DatabaseStack",
    db_config=DB_CONFIG,
    env=ENV,
    env_name=ENV_NAME,
)
CERT_STACK = PaV3CertStack(
    APP,
    "PaV3CertStack",
    network_config=NETWORK_CONFIG,
    env=CERT_ENV,
    cross_region_references=True,
)
DUMMY_IMAGE = ecs.ContainerImage.from_registry(
    "public.ecr.aws/docker/library/nginx:stable"
)
with patch("aws_cdk.aws_ecs.ContainerImage.from_asset", return_value=DUMMY_IMAGE):
    APP_STACK = PolicyAtlasStack(
        APP,
        "PaV3AppStack",
        pa_config=PA_CONFIG,
        certificate=CERT_STACK.certificate,
        env=ENV,
        env_name=ENV_NAME,
        cross_region_references=True,
    )

ASSEMBLY = APP.synth()
TEMPLATES = {
    "network": Template.from_stack(NETWORK_STACK).to_json(),
    "database": Template.from_stack(DATABASE_STACK).to_json(),
    "cert": Template.from_stack(CERT_STACK).to_json(),
    "app": Template.from_stack(APP_STACK).to_json(),
}
RENDERED_TEMPLATES = {
    stack_name: json.dumps(template, sort_keys=True)
    for stack_name, template in TEMPLATES.items()
}
ALL_RENDERED_TEMPLATES = "\n".join(RENDERED_TEMPLATES.values())


def test_all_stacks_synth_without_aws_calls():
    assert all(template["Resources"] for template in TEMPLATES.values())


def test_namespacing_table_is_rendered_in_its_designated_stacks():
    for surface, v3_name, stack_names in NAMESPACING_CASES:
        for stack_name in stack_names:
            assert v3_name in RENDERED_TEMPLATES[stack_name], (
                f"{surface} ({v3_name}) missing from {stack_name} template"
            )


def test_ssm_parameters_use_only_the_v3_prefix():
    parameter_names = [
        resource["Properties"]["Name"]
        for template in TEMPLATES.values()
        for _, resource in _resources(template, "AWS::SSM::Parameter")
    ]
    assert parameter_names
    assert all(name.startswith(SSM_PREFIX) for name in parameter_names)
    assert SSM_PREFIX in ALL_RENDERED_TEMPLATES


def test_no_template_contains_a_v2_ssm_prefix_or_backend_task_family():
    assert "/policy_atlas/" not in ALL_RENDERED_TEMPLATES
    assert '"Family": "policy-atlas-backend"' not in ALL_RENDERED_TEMPLATES


def test_removed_service_discovery_and_autoscaling_resources_are_absent():
    resource_types = [
        resource["Type"]
        for template in TEMPLATES.values()
        for resource in template["Resources"].values()
    ]
    assert not [name for name in resource_types if name.startswith("AWS::ServiceDiscovery::")]
    assert not [name for name in resource_types if name.startswith("AWS::ApplicationAutoScaling::")]


def test_database_stack_only_contains_load_secret_lambda_and_no_ecs_resources():
    # `triggers.Trigger` adds CDK's own provider Lambda.  It is framework
    # plumbing, not an application/deploy Lambda; all authored functions must
    # therefore reduce to this one load-secret handler.
    lambda_functions = [
        function
        for function in _resources(TEMPLATES["database"], "AWS::Lambda::Function")
        if not function[0].startswith("AWSCDKTriggerCustomResourceProvider")
    ]
    assert len(lambda_functions) == 1
    assert lambda_functions[0][0].startswith("LoadSecretFunction")
    database_resource_types = {
        resource["Type"] for resource in TEMPLATES["database"]["Resources"].values()
    }
    assert "AWS::ECS::Service" not in database_resource_types
    assert "AWS::ECS::TaskDefinition" not in database_resource_types


def test_no_rendered_container_or_environment_mentions_removed_products():
    lowered = ALL_RENDERED_TEMPLATES.lower()
    for removed_name in ("supabase", "postgrest", "clerk"):
        assert removed_name not in lowered


def test_app_stack_deploy_invariant_values_are_template_pinned():
    _, service = _resources(TEMPLATES["app"], "AWS::ECS::Service")[0]
    service_properties = service["Properties"]
    assert service_properties["DesiredCount"] == 0
    deployment = service_properties["DeploymentConfiguration"]
    assert deployment["MinimumHealthyPercent"] == 0
    assert deployment["MaximumPercent"] == 100

    _, task_definition = _resources(TEMPLATES["app"], "AWS::ECS::TaskDefinition")[0]
    assert task_definition["Properties"]["ContainerDefinitions"][0]["StopTimeout"] == 10

    _, target_group = _resources(
        TEMPLATES["app"], "AWS::ElasticLoadBalancingV2::TargetGroup"
    )[0]
    assert target_group["Properties"]["HealthCheckPath"] == "/readyz"


def test_aurora_security_group_has_only_expected_5432_ingress():
    database_rules = _port_5432_ingress(TEMPLATES["database"])
    app_rules = _port_5432_ingress(TEMPLATES["app"])
    assert len(database_rules) + len(app_rules) == 4

    db_security_group_id = next(
        logical_id
        for logical_id, _ in _resources(TEMPLATES["database"], "AWS::EC2::SecurityGroup")
        if logical_id.startswith("DBSecurityGroup")
    )
    db_group_reference = {"Fn::GetAtt": [db_security_group_id, "GroupId"]}
    assert all(rule["GroupId"] == db_group_reference for rule in database_rules)

    migration_rule = next(
        rule for rule in database_rules if "MigrationLambdaSG" in json.dumps(rule)
    )
    fck_nat_rule = next(
        rule
        for rule in database_rules
        if "SsmParameterValuepolicyatlasv3networkfcknatsgid" in json.dumps(rule)
    )
    jumpbox_rule = next(
        rule for rule in database_rules if "NestaDBJumpbox" in json.dumps(rule)
    )
    assert "MigrationLambdaSG" in json.dumps(migration_rule["SourceSecurityGroupId"])
    assert "SsmParameterValuepolicyatlasv3networkfcknatsgid" in json.dumps(
        fck_nat_rule["SourceSecurityGroupId"]
    )
    assert "NestaDBJumpbox" in json.dumps(jumpbox_rule["SourceSecurityGroupId"])

    assert len(app_rules) == 1
    api_rule = app_rules[0]
    assert "SsmParameterValuepolicyatlasv3dbsecuritygroupid" in json.dumps(
        api_rule["GroupId"]
    )
    assert "BackendSG" in json.dumps(api_rule["SourceSecurityGroupId"])


def test_jumpbox_output_forwards_to_the_cluster_endpoint():
    outputs = json.dumps(TEMPLATES["database"]["Outputs"], sort_keys=True)
    assert "AWS-StartPortForwardingSessionToRemoteHost" in outputs
    assert "PortForwardingCommand" in outputs
    assert "NestaDBJumpbox" in outputs
    assert "Endpoint.Address" in outputs
    assert 'localPortNumber=\\\"15432\\\"' in outputs


def test_fck_nat_role_has_ssm_managed_instance_policy():
    # The fck-nat instance role is the only IAM role this stack synthesizes;
    # pin that so the any-role check below cannot silently pass on an
    # unrelated role if the stack grows one.
    roles = _resources(TEMPLATES["network"], "AWS::IAM::Role")
    assert len(roles) == 1
    document = json.dumps(roles[0][1]["Properties"], sort_keys=True)
    assert "AmazonSSMManagedInstanceCore" in document


def test_aurora_cluster_is_snapshot_on_deletion():
    _, cluster = _resources(TEMPLATES["database"], "AWS::RDS::DBCluster")[0]
    assert cluster["DeletionPolicy"] == "Snapshot"


def test_aurora_cluster_is_encrypted_guarded_and_backed_up():
    # Review-stack hardening pins (026 step 7): encryption at rest, deletion
    # protection, 7-day backups — template-asserted like the 5432 invariant.
    _, cluster = _resources(TEMPLATES["database"], "AWS::RDS::DBCluster")[0]
    properties = cluster["Properties"]
    assert properties["StorageEncrypted"] is True
    assert properties["DeletionProtection"] is True
    assert properties["BackupRetentionPeriod"] == 7


def test_vpc_lookup_context_queries_are_filtered_by_vpc_name_tag():
    # `CloudAssembly.manifest` presently cannot deserialize manifests containing
    # lookup-only stack artifacts (their templateFile is undefined).  CDK's
    # documented cloud-assembly contract is the emitted manifest.json, whose
    # `missing` list is exactly the context queries the CLI resolves.
    manifest_path = Path(ASSEMBLY.directory) / "manifest.json"
    missing_context = json.loads(manifest_path.read_text())["missing"]
    vpc_queries = [
        query for query in missing_context if query["provider"] == "vpc-provider"
    ]
    assert vpc_queries, "expected Vpc.from_lookup to emit vpc-provider context queries"
    for query in vpc_queries:
        assert query["props"]["filter"]["tag:Name"] == VPC_NAME


def test_cognito_user_pool_is_operator_managed_and_retained():
    _, user_pool = _resources(TEMPLATES["app"], "AWS::Cognito::UserPool")[0]
    properties = user_pool["Properties"]
    assert user_pool["DeletionPolicy"] == "Retain"
    assert properties["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"] is True
    assert properties["AutoVerifiedAttributes"] == ["email"]
    assert properties["UsernameAttributes"] == ["email"]
    assert properties["AccountRecoverySetting"] == {
        "RecoveryMechanisms": [{"Name": "verified_email", "Priority": 1}]
    }


def test_cognito_spa_client_is_public_code_flow_with_exact_redirects():
    _, client = _resources(TEMPLATES["app"], "AWS::Cognito::UserPoolClient")[0]
    properties = client["Properties"]
    urls = ["https://v3.policyatlas.uk", "https://v3.policyatlas.uk/"]
    assert properties["GenerateSecret"] is False
    assert properties["AllowedOAuthFlowsUserPoolClient"] is True
    assert properties["AllowedOAuthFlows"] == ["code"]
    assert properties["AllowedOAuthScopes"] == ["openid", "email", "profile"]
    assert properties["CallbackURLs"] == urls
    assert properties["LogoutURLs"] == urls
    # Review-stack pins (026 step 7; refresh length is the owner's call —
    # 30 d kept, 2026-07-28): explicit token validities and no
    # user-enumeration oracle.
    assert properties["AccessTokenValidity"] == 60
    assert properties["RefreshTokenValidity"] == 43200  # 30 d, rendered in minutes
    assert properties["TokenValidityUnits"] == {
        "AccessToken": "minutes",
        "RefreshToken": "minutes",
    }
    assert properties["PreventUserExistenceErrors"] == "ENABLED"


def test_cognito_hosted_ui_uses_the_fixed_prefix():
    _, domain = _resources(TEMPLATES["app"], "AWS::Cognito::UserPoolDomain")[0]
    assert domain["Properties"]["Domain"] == "policy-atlas-v3"


def test_cloudfront_uses_oac_with_spa_fallback_and_certificate():
    app_template = TEMPLATES["app"]
    assert len(_resources(app_template, "AWS::CloudFront::OriginAccessControl")) == 1
    assert not _resources(app_template, "AWS::CloudFront::CloudFrontOriginAccessIdentity")

    _, distribution = _resources(app_template, "AWS::CloudFront::Distribution")[0]
    config = distribution["Properties"]["DistributionConfig"]
    assert config["Aliases"] == ["v3.policyatlas.uk"]
    assert config["DefaultRootObject"] == "index.html"
    assert "PaV3CertStack" in json.dumps(
        config["ViewerCertificate"]["AcmCertificateArn"]
    )
    assert all("OriginAccessControlId" in origin for origin in config["Origins"])
    # Review-stack hardening pin (026 step 7): the managed SecurityHeadersPolicy
    # (HSTS etc.) on the default and /index.html behaviors.
    security_headers_policy_id = "67f7725c-6f97-4210-82d7-5512b31e9d03"
    assert (
        config["DefaultCacheBehavior"]["ResponseHeadersPolicyId"]
        == security_headers_policy_id
    )
    assert all(
        behavior["ResponseHeadersPolicyId"] == security_headers_policy_id
        for behavior in config["CacheBehaviors"]
    )
    assert {
        (response["ErrorCode"], response["ResponseCode"], response["ResponsePagePath"])
        for response in config["CustomErrorResponses"]
    } == {
        (403, 200, "/index.html"),
        (404, 200, "/index.html"),
    }

    index_behavior = config["CacheBehaviors"][0]
    assert index_behavior["PathPattern"] == "/index.html"
    index_policy = _resources(app_template, "AWS::CloudFront::CachePolicy")[0][1]
    assert index_policy["Properties"]["CachePolicyConfig"]["MaxTTL"] == 60


def test_frontend_apex_has_a_and_aaaa_cloudfront_aliases():
    distribution_id = _resources(
        TEMPLATES["app"], "AWS::CloudFront::Distribution"
    )[0][0]
    cloudfront_aliases = [
        resource["Properties"]
        for _, resource in _resources(TEMPLATES["app"], "AWS::Route53::RecordSet")
        if resource["Properties"].get("AliasTarget", {}).get("DNSName")
        == {"Fn::GetAtt": [distribution_id, "DomainName"]}
    ]
    assert {record["Type"] for record in cloudfront_aliases} == {"A", "AAAA"}
    assert all(record["Name"] == "v3.policyatlas.uk." for record in cloudfront_aliases)


def test_frontend_and_fonts_buckets_are_private_and_fonts_are_destroyed():
    buckets = _resources(TEMPLATES["app"], "AWS::S3::Bucket")
    assert len(buckets) == 2
    assert all(
        bucket["Properties"]["PublicAccessBlockConfiguration"] == {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True,
        }
        for _, bucket in buckets
    )
    fonts_bucket = next(bucket for logical_id, bucket in buckets if logical_id.startswith("FontsBucket"))
    assert fonts_bucket["DeletionPolicy"] == "Delete"


def test_auth_and_deploy_ssm_exports_are_present():
    parameter_names = {
        resource["Properties"]["Name"]
        for _, resource in _resources(TEMPLATES["app"], "AWS::SSM::Parameter")
    }
    assert {
        "/policy_atlas_v3/auth/user_pool_id",
        "/policy_atlas_v3/auth/issuer",
        "/policy_atlas_v3/auth/jwks_url",
        "/policy_atlas_v3/auth/client_id",
        "/policy_atlas_v3/auth/hosted_domain",
        "/policy_atlas_v3/deploy/frontend_bucket_name",
        "/policy_atlas_v3/deploy/fonts_bucket_name",
        "/policy_atlas_v3/deploy/distribution_id",
    } <= parameter_names


def test_cert_stack_is_dns_validated_for_the_apex_only():
    _, certificate = _resources(TEMPLATES["cert"], "AWS::CertificateManager::Certificate")[0]
    properties = certificate["Properties"]
    assert properties["DomainName"] == "v3.policyatlas.uk"
    assert "SubjectAlternativeNames" not in properties
    assert properties["ValidationMethod"] == "DNS"


def test_cert_stack_uses_its_namespaced_cloudformation_id():
    manifest_path = Path(ASSEMBLY.directory) / "manifest.json"
    artifacts = json.loads(manifest_path.read_text())["artifacts"]
    assert "PaV3CertStack" in artifacts
