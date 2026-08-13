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
import pytest
from aws_cdk import Environment, aws_ec2 as ec2, aws_ecs as ecs, aws_rds as rds
from aws_cdk.assertions import Template

from infra.components.nesta_db_jumpbox import NestaDBJumpbox
from infra.components.nesta_ssm_endpoints import (
    SsmConnectivity,
    SsmConnectivityMode,
    SsmVpcEndpoints,
)
from infra.database_stack import DatabaseStack
from infra.cert_stack import PaV3CertStack
from infra.cognito_auth import CognitoAuth
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
    ssm_connectivity=NETWORK_STACK.ssm_connectivity,
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
    assert len(database_rules) + len(app_rules) == 3

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
    jumpbox_rule = next(
        rule for rule in database_rules if "NestaDBJumpbox" in json.dumps(rule)
    )
    assert "MigrationLambdaSG" in json.dumps(migration_rule["SourceSecurityGroupId"])
    assert "NestaDBJumpbox" in json.dumps(jumpbox_rule["SourceSecurityGroupId"])
    assert not any(
        "SsmParameterValuepolicyatlasv3networkfcknatsgid" in json.dumps(rule)
        for rule in database_rules
    )

    assert len(app_rules) == 1
    api_rule = app_rules[0]
    assert "SsmParameterValuepolicyatlasv3dbsecuritygroupid" in json.dumps(
        api_rule["GroupId"]
    )
    assert "BackendSG" in json.dumps(api_rule["SourceSecurityGroupId"])


def test_backend_to_aurora_route_is_vpc_local_and_nat_independent():
    db_sg_id, db_sg = next(
        resource
        for resource in _resources(TEMPLATES["database"], "AWS::EC2::SecurityGroup")
        if resource[0].startswith("DBSecurityGroup")
    )
    backend_sg_id, backend_sg = next(
        resource
        for resource in _resources(TEMPLATES["app"], "AWS::EC2::SecurityGroup")
        if resource[0].startswith("BackendSG")
    )
    _, db_subnet_group = _resources(
        TEMPLATES["database"], "AWS::RDS::DBSubnetGroup"
    )[0]
    _, backend_service = _resources(TEMPLATES["app"], "AWS::ECS::Service")[0]
    backend_networking = backend_service["Properties"]["NetworkConfiguration"][
        "AwsvpcConfiguration"
    ]

    # Both ENIs are placed in the same private VPC/subnets. AWS's implicit VPC
    # local route carries this traffic; the default route through fck-nat is
    # relevant only to internet-bound traffic.
    assert db_sg["Properties"]["VpcId"] == backend_sg["Properties"]["VpcId"]
    assert set(db_subnet_group["Properties"]["SubnetIds"]) == set(
        backend_networking["Subnets"]
    )
    private_routes = [
        resource["Properties"]
        for logical_id, resource in _resources(
            TEMPLATES["network"], "AWS::EC2::Route"
        )
        if "PrivateSubnet" in logical_id
    ]
    assert private_routes
    assert all(
        route["DestinationCidrBlock"] == "0.0.0.0/0"
        and "FckNatInterface" in json.dumps(route["NetworkInterfaceId"])
        for route in private_routes
    )
    assert backend_networking["AssignPublicIp"] == "DISABLED"
    assert backend_networking["SecurityGroups"] == [
        {"Fn::GetAtt": [backend_sg_id, "GroupId"]}
    ]

    api_rule = _port_5432_ingress(TEMPLATES["app"])[0]
    assert api_rule["SourceSecurityGroupId"] == {
        "Fn::GetAtt": [backend_sg_id, "GroupId"]
    }
    assert "SsmParameterValuepolicyatlasv3dbsecuritygroupid" in json.dumps(
        api_rule["GroupId"]
    )
    assert db_sg_id not in json.dumps(api_rule["GroupId"])
    assert "fcknat" not in json.dumps(api_rule).lower()


def test_jumpbox_document_fixes_the_remote_target_and_port():
    documents = _resources(TEMPLATES["database"], "AWS::SSM::Document")
    assert len(documents) == 1
    document_id, document = documents[0]
    properties = document["Properties"]
    content = properties["Content"]

    # Omitting Name lets CloudFormation make this reusable construct unique.
    assert "Name" not in properties
    assert properties["DocumentType"] == "Session"
    assert properties["DocumentFormat"] == "JSON"
    assert properties["TargetType"] == "/AWS::EC2::Instance"
    assert properties["UpdateMethod"] == "NewVersion"
    assert content["sessionType"] == "Port"
    assert set(content["parameters"]) == {"localPortNumber"}
    assert content["parameters"]["localPortNumber"]["default"] == "15432"
    assert content["properties"]["type"] == "LocalPortForwarding"
    cluster_id = _resources(TEMPLATES["database"], "AWS::RDS::DBCluster")[0][0]
    assert content["properties"]["host"] == {
        "Fn::GetAtt": [cluster_id, "Endpoint.Address"]
    }
    assert content["properties"]["portNumber"] == "5432"
    assert content["properties"]["localPortNumber"] == "{{ localPortNumber }}"

    outputs = json.dumps(TEMPLATES["database"]["Outputs"], sort_keys=True)
    assert "PortForwardingCommand" in outputs
    assert "NestaDBJumpbox" in outputs
    assert document_id in outputs
    assert "AWS-StartPortForwardingSessionToRemoteHost" not in outputs
    assert "Endpoint.Address" not in outputs
    assert "host=" not in outputs
    assert "portNumber=" not in outputs


def test_jumpbox_networking_is_deny_by_default_and_database_scoped():
    database_template = TEMPLATES["database"]
    jumpbox_sg_id, jumpbox_sg = next(
        resource
        for resource in _resources(database_template, "AWS::EC2::SecurityGroup")
        if "NestaDBJumpbox" in resource[0]
    )
    assert jumpbox_sg["Properties"]["SecurityGroupEgress"] == [
        {
            "CidrIp": "0.0.0.0/0",
            "Description": "Allow jumpbox to connect to the internet for SSM",
            "FromPort": 443,
            "IpProtocol": "tcp",
            "ToPort": 443,
        }
    ]

    database_egress = next(
        resource["Properties"]
        for _, resource in _resources(
            database_template, "AWS::EC2::SecurityGroupEgress"
        )
        if resource["Properties"].get("GroupId")
        == {"Fn::GetAtt": [jumpbox_sg_id, "GroupId"]}
    )
    assert database_egress["FromPort"] == 5432
    assert database_egress["ToPort"] == 5432
    assert "DBSecurityGroup" in json.dumps(
        database_egress["DestinationSecurityGroupId"]
    )

    _, instance = next(
        resource
        for resource in _resources(database_template, "AWS::EC2::Instance")
        if "NestaDBJumpbox" in resource[0]
    )
    instance_properties = instance["Properties"]
    assert instance_properties["InstanceType"] == "t4g.nano"
    assert "arm64" in json.dumps(instance_properties["ImageId"])
    assert instance_properties["NetworkInterfaces"][0][
        "AssociatePublicIpAddress"
    ] is False
    _, launch_template = _resources(
        database_template, "AWS::EC2::LaunchTemplate"
    )[0]
    assert launch_template["Properties"]["LaunchTemplateData"]["MetadataOptions"][
        "HttpTokens"
    ] == "required"

    _, instance_role = next(
        resource
        for resource in _resources(database_template, "AWS::IAM::Role")
        if "NestaDBJumpbox" in resource[0]
    )
    assert "AmazonSSMManagedInstanceCore" in json.dumps(
        instance_role["Properties"]["ManagedPolicyArns"]
    )


def test_staging_uses_nat_without_interface_endpoints():
    assert NETWORK_STACK.ssm_connectivity.mode is SsmConnectivityMode.NAT
    assert not _resources(TEMPLATES["network"], "AWS::EC2::VPCEndpoint")
    assert not _resources(TEMPLATES["database"], "AWS::EC2::VPCEndpoint")


def test_network_stack_owns_endpoints_when_configured():
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    config = {**NETWORK_CONFIG, "ssm_connectivity": "interface_endpoints"}
    stack = NetworkStack(
        app,
        "ProductionNetworkStack",
        network_config=config,
        env=ENV,
        aws_region=config["aws_region"],
        env_name="production",
    )

    template = Template.from_stack(stack).to_json()
    assert stack.ssm_connectivity.mode is SsmConnectivityMode.INTERFACE_ENDPOINTS
    assert stack.ssm_endpoints is not None
    assert len(_resources(template, "AWS::EC2::VPCEndpoint")) == 2


def test_production_database_imports_only_the_network_managed_node_group():
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    config = {**NETWORK_CONFIG, "ssm_connectivity": "interface_endpoints"}
    network_stack = NetworkStack(
        app,
        "ProductionNetworkStack",
        network_config=config,
        env=ENV,
        aws_region=config["aws_region"],
        env_name="production",
    )
    database_stack = DatabaseStack(
        app,
        "ProductionDatabaseStack",
        db_config=DB_CONFIG,
        env=ENV,
        env_name="production",
        ssm_connectivity=network_stack.ssm_connectivity,
    )

    app.synth()
    network_template = Template.from_stack(network_stack).to_json()
    database_template = Template.from_stack(database_stack).to_json()
    assert len(_resources(network_template, "AWS::EC2::VPCEndpoint")) == 2
    assert not _resources(database_template, "AWS::EC2::VPCEndpoint")

    _, instance = next(
        resource
        for resource in _resources(database_template, "AWS::EC2::Instance")
        if "NestaDBJumpbox" in resource[0]
    )
    attached_groups = instance["Properties"]["NetworkInterfaces"][0]["GroupSet"]
    imported_groups = [
        group for group in attached_groups if "Fn::ImportValue" in group
    ]
    assert len(imported_groups) == 1
    assert "ManagedNodeEndpointSG" in json.dumps(imported_groups[0])


def test_endpoint_connectivity_is_network_owned_and_attached_to_jumpbox():
    app = cdk.App()
    stack = cdk.Stack(app, "EndpointJumpboxStack", env=ENV)
    vpc = ec2.Vpc(stack, "Vpc", max_azs=1)
    endpoints = SsmVpcEndpoints(stack, "SsmEndpoints", vpc=vpc)
    db_sg = ec2.SecurityGroup(stack, "DatabaseSG", vpc=vpc)
    cluster = rds.DatabaseCluster.from_database_cluster_attributes(
        stack,
        "ImportedCluster",
        cluster_identifier="imported-cluster",
        cluster_endpoint_address="database.example.internal",
        port=5432,
    )

    NestaDBJumpbox(
        stack,
        "EndpointJumpbox",
        vpc=vpc,
        ssm_connectivity=endpoints.connectivity,
        db_cluster=cluster,
        db_sg=db_sg,
    )

    template = Template.from_stack(stack).to_json()
    endpoint_sg_id = next(
        logical_id
        for logical_id, _ in _resources(template, "AWS::EC2::SecurityGroup")
        if "SSMEndpointSG" in logical_id
    )
    managed_node_sg_id = next(
        logical_id
        for logical_id, _ in _resources(template, "AWS::EC2::SecurityGroup")
        if "ManagedNodeEndpointSG" in logical_id
    )
    jumpbox_sg_id = next(
        logical_id
        for logical_id, _ in _resources(template, "AWS::EC2::SecurityGroup")
        if "EndpointJumpboxEndpointJumpboxSG" in logical_id
    )

    interface_endpoints = _resources(template, "AWS::EC2::VPCEndpoint")
    assert len(interface_endpoints) == 2
    endpoint_services = json.dumps(interface_endpoints, sort_keys=True)
    assert ".ssm" in endpoint_services
    assert ".ssmmessages" in endpoint_services
    assert all(
        resource["Properties"]["VpcEndpointType"] == "Interface"
        and resource["Properties"]["PrivateDnsEnabled"] is True
        and resource["Properties"]["SecurityGroupIds"]
        == [{"Fn::GetAtt": [endpoint_sg_id, "GroupId"]}]
        for _, resource in interface_endpoints
    )

    endpoint_ingress = next(
        resource["Properties"]
        for _, resource in _resources(template, "AWS::EC2::SecurityGroupIngress")
        if resource["Properties"].get("GroupId")
        == {"Fn::GetAtt": [endpoint_sg_id, "GroupId"]}
    )
    assert endpoint_ingress["SourceSecurityGroupId"] == {
        "Fn::GetAtt": [managed_node_sg_id, "GroupId"]
    }
    assert endpoint_ingress["FromPort"] == endpoint_ingress["ToPort"] == 443

    managed_node_egress = next(
        resource["Properties"]
        for _, resource in _resources(template, "AWS::EC2::SecurityGroupEgress")
        if resource["Properties"].get("GroupId")
        == {"Fn::GetAtt": [managed_node_sg_id, "GroupId"]}
    )
    assert managed_node_egress["DestinationSecurityGroupId"] == {
        "Fn::GetAtt": [endpoint_sg_id, "GroupId"]
    }
    assert managed_node_egress["FromPort"] == managed_node_egress["ToPort"] == 443

    _, instance = next(
        resource
        for resource in _resources(template, "AWS::EC2::Instance")
        if "EndpointJumpbox" in resource[0]
    )
    attached_groups = instance["Properties"]["NetworkInterfaces"][0]["GroupSet"]
    assert {"Fn::GetAtt": [jumpbox_sg_id, "GroupId"]} in attached_groups
    assert {"Fn::GetAtt": [managed_node_sg_id, "GroupId"]} in attached_groups
    assert "0.0.0.0/0" not in json.dumps(
        [
            resource
            for resource in _resources(template, "AWS::EC2::SecurityGroupEgress")
            if resource[1]["Properties"].get("FromPort") == 443
        ]
    )


def test_ssm_connectivity_rejects_incomplete_or_ambiguous_policies():
    app = cdk.App()
    stack = cdk.Stack(app, "InvalidConnectivityStack")
    vpc = ec2.Vpc(stack, "Vpc", max_azs=1)
    security_group = ec2.SecurityGroup(stack, "ManagedNodeSG", vpc=vpc)

    with pytest.raises(ValueError, match="must not provide"):
        SsmConnectivity(
            mode=SsmConnectivityMode.NAT,
            managed_node_security_group=security_group,
        )
    with pytest.raises(ValueError, match="requires a managed-node"):
        SsmConnectivity(mode=SsmConnectivityMode.INTERFACE_ENDPOINTS)
    with pytest.raises(ValueError, match="must be a SsmConnectivityMode"):
        SsmConnectivity(mode="nat")


def test_jumpbox_local_mode_does_not_require_a_remote_endpoint():
    app = cdk.App()
    stack = cdk.Stack(app, "LocalOnlyJumpboxStack", env=ENV)
    vpc = ec2.Vpc(stack, "Vpc", max_azs=1)
    db_sg = ec2.SecurityGroup(stack, "DatabaseSG", vpc=vpc)

    NestaDBJumpbox(
        stack,
        "LocalOnlyJumpbox",
        vpc=vpc,
        ssm_connectivity=SsmConnectivity.via_nat(),
        db_sg=db_sg,
        remote_mode=False,
        local_mode=True,
    )

    template = Template.from_stack(stack).to_json()
    assert not _resources(template, "AWS::SSM::Document")
    assert "PortForwardingCommand" not in json.dumps(
        template.get("Outputs", {}), sort_keys=True
    )


def test_imported_cluster_accepts_an_explicit_security_group_override():
    app = cdk.App()
    stack = cdk.Stack(app, "ImportedClusterJumpboxStack", env=ENV)
    vpc = ec2.Vpc(stack, "Vpc", max_azs=1)
    db_sg = ec2.SecurityGroup(stack, "DatabaseSG", vpc=vpc)
    cluster = rds.DatabaseCluster.from_database_cluster_attributes(
        stack,
        "ImportedCluster",
        cluster_identifier="imported-cluster",
        cluster_endpoint_address="database.example.internal",
        port=5432,
    )

    NestaDBJumpbox(
        stack,
        "ImportedClusterJumpbox",
        vpc=vpc,
        ssm_connectivity=SsmConnectivity.via_nat(),
        db_cluster=cluster,
        db_sg=db_sg,
    )

    template = Template.from_stack(stack).to_json()
    assert len(_resources(template, "AWS::SSM::Document")) == 1


@pytest.mark.parametrize("port", [False, 0, 65536, "5432"])
def test_jumpbox_rejects_invalid_database_ports(port):
    app = cdk.App()
    stack = cdk.Stack(app, f"InvalidPortJumpboxStack{str(port).replace('-', '')}")
    vpc = ec2.Vpc(stack, "Vpc", max_azs=1)
    db_sg = ec2.SecurityGroup(stack, "DatabaseSG", vpc=vpc)

    with pytest.raises(ValueError, match="db_port must be an integer"):
        NestaDBJumpbox(
            stack,
            "InvalidPortJumpbox",
            vpc=vpc,
            ssm_connectivity=SsmConnectivity.via_nat(),
            db_sg=db_sg,
            remote_mode=False,
            local_mode=True,
            db_port=port,
        )


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


def test_cognito_auth_uses_supplied_public_and_hosted_ui_domains():
    app = cdk.App()
    stack = cdk.Stack(app, "ConfigurableCognitoStack")
    CognitoAuth(
        stack,
        "CognitoAuth",
        domain_name="policy.example.test",
        domain_prefix="policy-atlas-production-test",
    )
    template = Template.from_stack(stack).to_json()

    _, client = _resources(template, "AWS::Cognito::UserPoolClient")[0]
    urls = ["https://policy.example.test", "https://policy.example.test/"]
    assert client["Properties"]["CallbackURLs"] == urls
    assert client["Properties"]["LogoutURLs"] == urls

    _, domain = _resources(template, "AWS::Cognito::UserPoolDomain")[0]
    assert domain["Properties"]["Domain"] == "policy-atlas-production-test"


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
