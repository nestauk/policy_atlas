"""Task 057 (N4, N5, N11): the queued ingest worker and its alarms, pinned value by value.

Each test reads the synthesized templates built once in ``test_synth``.
"""
import json
import re
from pathlib import Path

import pytest

from tests.unit.test_synth import (
    ASSEMBLY,
    BACKEND_IMAGE_ASSET_CALLS,
    IN_PROCESS_APP_TEMPLATE,
    INFRA_ROOT,
    TEMPLATES,
    _resources,
)

APP = TEMPLATES["app"]
INGEST_ENVIRONMENT_NAMES = {"POLICY_ATLAS_DB_SECRET_ARN", "POLICY_ATLAS_MODEL_ROUTE", "LOG_FORMAT"}
DB_SECRET_PARAMETER = "SsmParameterValuepolicyatlasv3dbsecretname"
DB_SG_PARAMETER = "SsmParameterValuepolicyatlasv3dbsecuritygroupid"


def _one(resource_type: str, prefix: str, template: dict = APP) -> tuple[str, dict]:
    matches = [
        (logical_id, resource)
        for logical_id, resource in _resources(template, resource_type)
        if logical_id.startswith(prefix)
    ]
    assert len(matches) == 1, (resource_type, prefix, [m[0] for m in matches])
    return matches[0]


def _queue(prefix: str) -> tuple[str, dict]:
    return _one("AWS::SQS::Queue", prefix)


def _function() -> tuple[str, dict]:
    return _one("AWS::Lambda::Function", "IngestFunction")


def _function_policy_statements() -> list[dict]:
    _, function = _function()
    role_id = function["Properties"]["Role"]["Fn::GetAtt"][0]
    return [
        statement
        for _, policy in _resources(APP, "AWS::IAM::Policy")
        if {"Ref": role_id} in policy["Properties"]["Roles"]
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
    ]


def _alarm(template: dict, name: str) -> dict:
    alarms = [
        resource["Properties"]
        for _, resource in _resources(template, "AWS::CloudWatch::Alarm")
        if resource["Properties"].get("AlarmName") == name
    ]
    assert len(alarms) == 1, name
    return alarms[0]


def _api_environment(template: dict) -> dict:
    task_definition = next(
        resource["Properties"]
        for _, resource in _resources(template, "AWS::ECS::TaskDefinition")
        if resource["Properties"]["Family"] == "policy-atlas-v3-api"
    )
    container = task_definition["ContainerDefinitions"][0]
    return {item["Name"]: item["Value"] for item in container["Environment"]}


# --- Queue and dead-letter queue (N4, N11) ---


def test_ingest_queue_retention_encryption_visibility_and_dead_letter_after_two_tries():
    dead_letter_id, _ = _queue("IngestDeadLetterQueue")
    _, queue = _queue("IngestQueue")
    properties = queue["Properties"]
    assert properties["QueueName"] == "policy-atlas-v3-ingest"
    assert properties["MessageRetentionPeriod"] == 4 * 24 * 3600
    assert properties["SqsManagedSseEnabled"] is True
    # Visibility timeout = function timeout (180 s) + 30 s.
    _, function = _function()
    assert properties["VisibilityTimeout"] == function["Properties"]["Timeout"] + 30 == 210
    assert properties["RedrivePolicy"] == {
        "deadLetterTargetArn": {"Fn::GetAtt": [dead_letter_id, "Arn"]},
        "maxReceiveCount": 2,
    }


def test_dead_letter_queue_is_encrypted_and_kept_fourteen_days():
    _, dead_letter = _queue("IngestDeadLetterQueue")
    properties = dead_letter["Properties"]
    assert properties["QueueName"] == "policy-atlas-v3-ingest-dlq"
    assert properties["SqsManagedSseEnabled"] is True
    assert properties["MessageRetentionPeriod"] == 14 * 24 * 3600
    assert "RedrivePolicy" not in properties


def test_both_queues_refuse_unencrypted_transport():
    for prefix in ("IngestQueuePolicy", "IngestDeadLetterQueuePolicy"):
        _, policy = _one("AWS::SQS::QueuePolicy", prefix)
        (statement,) = policy["Properties"]["PolicyDocument"]["Statement"]
        assert statement["Effect"] == "Deny"
        assert statement["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}


# --- Function (N4, N11, D5, D6) ---


def test_ingest_function_sizing_and_image_command():
    _, function = _function()
    properties = function["Properties"]
    assert properties["FunctionName"] == "policy-atlas-v3-ingest"
    assert properties["PackageType"] == "Image"
    assert properties["Timeout"] == 180
    assert properties["MemorySize"] == 1769
    assert properties["EphemeralStorage"] == {"Size": 512}
    assert properties["Architectures"] == ["x86_64"]
    assert properties["ImageConfig"]["Command"] == [
        "python",
        "-m",
        "awslambdaric",
        "policy_atlas.ops.ingest_worker.handler",
    ]


def test_ingest_function_uses_the_same_backend_image_as_the_api_and_migration():
    """One build, one push: the function's image URI equals both task images."""
    _, function = _function()
    function_image = json.dumps(function["Properties"]["Code"]["ImageUri"])
    function_tag = re.search(r"container-assets-[^:]+:([0-9a-f]{64})", function_image).group(1)
    task_images = [
        json.dumps(resource["Properties"]["ContainerDefinitions"][0]["Image"])
        for _, resource in _resources(APP, "AWS::ECS::TaskDefinition")
    ]
    assert len(task_images) == 2
    assert all(function_tag in image for image in task_images)

    # The backend asset is created once per app stack, from ../backend.
    assert BACKEND_IMAGE_ASSET_CALLS
    assert all(call["directory"] == "../backend" for call in BACKEND_IMAGE_ASSET_CALLS)
    assets = json.loads(
        (Path(ASSEMBLY.directory) / "PaV3AppStack.assets.json").read_text()
    )
    assert list(assets["dockerImages"]) == [function_tag]


def test_ingest_function_runs_in_the_private_subnets_with_its_own_security_group():
    _, function = _function()
    vpc_config = function["Properties"]["VpcConfig"]
    sg_id, sg = _one("AWS::EC2::SecurityGroup", "IngestSecurityGroup")
    assert vpc_config["SecurityGroupIds"] == [{"Fn::GetAtt": [sg_id, "GroupId"]}]
    # Same private subnets as the API service (the VPC lookup's private ones).
    _, service = _resources(APP, "AWS::ECS::Service")[0]
    service_subnets = service["Properties"]["NetworkConfiguration"]["AwsvpcConfiguration"]["Subnets"]
    assert set(vpc_config["SubnetIds"]) == set(service_subnets)
    # Outbound only; nothing is allowed in.
    assert "SecurityGroupIngress" not in sg["Properties"]
    # Outbound is three rules (owner ruling 2026-11-04): 80 and 443 to the internet,
    # 5432 to the database group. Not "allow all".
    inline = sg["Properties"]["SecurityGroupEgress"]
    assert sorted((r["CidrIp"], r["IpProtocol"], r["FromPort"], r["ToPort"]) for r in inline) == [
        ("0.0.0.0/0", "tcp", 80, 80),
        ("0.0.0.0/0", "tcp", 443, 443),
    ]
    db_egress = [
        rule["Properties"]
        for _, rule in _resources(APP, "AWS::EC2::SecurityGroupEgress")
        if json.dumps(rule["Properties"]["GroupId"]) == json.dumps({"Fn::GetAtt": [sg_id, "GroupId"]})
    ]
    assert [(r["IpProtocol"], r["FromPort"], r["ToPort"]) for r in db_egress] == [("tcp", 5432, 5432)]
    assert "DestinationSecurityGroupId" in db_egress[0]
    assert not [
        rule
        for _, rule in _resources(APP, "AWS::EC2::SecurityGroupIngress")
        if json.dumps(rule["Properties"]["GroupId"]) == json.dumps({"Fn::GetAtt": [sg_id, "GroupId"]})
    ]


def test_database_security_group_admits_the_ingest_function_on_5432_only():
    sg_id, _ = _one("AWS::EC2::SecurityGroup", "IngestSecurityGroup")
    rules = [
        resource["Properties"]
        for _, resource in _resources(APP, "AWS::EC2::SecurityGroupIngress")
        if resource["Properties"].get("SourceSecurityGroupId") == {"Fn::GetAtt": [sg_id, "GroupId"]}
    ]
    assert len(rules) == 1
    (rule,) = rules
    assert (rule["IpProtocol"], rule["FromPort"], rule["ToPort"]) == ("tcp", 5432, 5432)
    assert DB_SG_PARAMETER in json.dumps(rule["GroupId"])


def test_ingest_function_environment_is_the_three_variables_and_holds_no_secret():
    _, function = _function()
    environment = function["Properties"]["Environment"]["Variables"]
    assert set(environment) == INGEST_ENVIRONMENT_NAMES
    assert environment["LOG_FORMAT"] == "json"
    # Same route as the API task.
    assert environment["POLICY_ATLAS_MODEL_ROUTE"] == _api_environment(APP)["POLICY_ATLAS_MODEL_ROUTE"]
    secret_arn = json.dumps(environment["POLICY_ATLAS_DB_SECRET_ARN"])
    assert ":secretsmanager:" in secret_arn
    assert DB_SECRET_PARAMETER in secret_arn
    # Nothing key-like: no password, token, key or connection string.
    key_like = re.compile(r"KEY|TOKEN|PASSWORD|SECRET(?!_ARN)|DATABASE_URL|BEARER", re.IGNORECASE)
    assert not [name for name in environment if key_like.search(name)]
    rendered = json.dumps(environment).lower()
    for fragment in ("db_connection_string", "openai", "bedrock_token", "langfuse", "policy_atlas_v3/app"):
        assert fragment not in rendered


def test_ingest_function_can_read_only_the_database_secret_and_has_no_bedrock_permission():
    statements = _function_policy_statements()
    rendered = json.dumps(statements)
    assert "bedrock" not in rendered.lower()

    secret_statements = [
        statement for statement in statements if "secretsmanager:GetSecretValue" in statement["Action"]
    ]
    assert len(secret_statements) == 1
    resource = json.dumps(secret_statements[0]["Resource"])
    assert DB_SECRET_PARAMETER in resource
    assert "policy_atlas_v3/app" not in resource

    _, function = _function()
    role_id = function["Properties"]["Role"]["Fn::GetAtt"][0]
    role = APP["Resources"][role_id]["Properties"]
    managed = json.dumps(role.get("ManagedPolicyArns", []))
    assert "Bedrock" not in managed
    assert "AWSLambdaBasicExecutionRole" in managed
    assert "AWSLambdaVPCAccessExecutionRole" in managed
    assert "Policies" not in role


def test_ingest_function_log_group_keeps_thirty_days():
    log_group_id, log_group = _one("AWS::Logs::LogGroup", "IngestLogGroup")
    assert log_group["Properties"]["LogGroupName"] == "/policy_atlas_v3/ingest"
    assert log_group["Properties"]["RetentionInDays"] == 30
    _, function = _function()
    assert function["Properties"]["LoggingConfig"]["LogGroup"] == {"Ref": log_group_id}


# --- Event-source mapping (N5) ---


def test_event_source_mapping_takes_one_message_at_a_time_with_a_cap_of_twenty():
    queue_id, _ = _queue("IngestQueue")
    function_id, _ = _function()
    (mapping,) = [resource["Properties"] for _, resource in _resources(APP, "AWS::Lambda::EventSourceMapping")]
    assert mapping["EventSourceArn"] == {"Fn::GetAtt": [queue_id, "Arn"]}
    assert mapping["FunctionName"] == {"Ref": function_id}
    assert mapping["BatchSize"] == 1
    assert mapping["MaximumBatchingWindowInSeconds"] == 0
    assert mapping["ScalingConfig"] == {"MaximumConcurrency": 20}
    assert mapping["FunctionResponseTypes"] == ["ReportBatchItemFailures"]


# --- API task side (N11) ---


def test_api_task_role_may_only_send_to_the_ingest_queue():
    queue_id, _ = _queue("IngestQueue")
    task_role_policies = [
        resource["Properties"]
        for logical_id, resource in _resources(APP, "AWS::IAM::Policy")
        if logical_id.startswith("PolicyAtlasBackendTaskDefTaskRole")
    ]
    (policy,) = task_role_policies
    (statement,) = policy["PolicyDocument"]["Statement"]
    assert statement["Effect"] == "Allow"
    assert "sqs:SendMessage" in statement["Action"]
    assert "sqs:GetQueueAttributes" in statement["Action"]
    assert not {"sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:PurgeQueue"} & set(statement["Action"])
    assert statement["Resource"] == {"Fn::GetAtt": [queue_id, "Arn"]}


def test_api_task_gets_the_queue_url_and_the_configured_ingest_mode():
    queue_id, _ = _queue("IngestQueue")
    staging = _api_environment(APP)
    assert staging["POLICY_ATLAS_INGEST_MODE"] == "queued"
    assert staging["POLICY_ATLAS_INGEST_QUEUE_URL"] == {"Ref": queue_id}
    in_process = _api_environment(IN_PROCESS_APP_TEMPLATE)
    assert in_process["POLICY_ATLAS_INGEST_MODE"] == "in_process"


def test_ingest_mode_is_set_per_environment_in_the_config():
    config = json.loads((INFRA_ROOT / "pa_config.json").read_text())
    modes = {
        env_name: env_config["policy_atlas_config"]["backend"]["ingest_mode"]
        for env_name, env_config in config.items()
    }
    assert modes == {"staging": "queued", "prod": "in_process"}


def test_an_unknown_ingest_mode_is_rejected_at_synth():
    import aws_cdk as cdk
    from aws_cdk import Environment

    from infra.policy_atlas_stack import PolicyAtlasStack
    from tests.unit.test_synth import CERT_STACK, DUMMY_ACCOUNT, PA_CONFIG

    bad_config = json.loads(json.dumps(PA_CONFIG))
    bad_config["policy_atlas_config"]["backend"]["ingest_mode"] = "lambda"
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    with pytest.raises(ValueError, match="ingest_mode"):
        PolicyAtlasStack(
            app,
            "BadIngestMode",
            pa_config=bad_config,
            certificate=CERT_STACK.certificate,
            env=Environment(account=DUMMY_ACCOUNT, region="eu-west-2"),
            env_name="staging",
        )


# --- Alarms (N4, N11) ---


def test_dead_letter_queue_depth_alarm():
    dead_letter_id, _ = _queue("IngestDeadLetterQueue")
    alarm = _alarm(APP, "policy-atlas-v3-ingest-dlq-depth")
    assert alarm["Namespace"] == "AWS/SQS"
    assert alarm["MetricName"] == "ApproximateNumberOfMessagesVisible"
    assert alarm["Dimensions"] == [
        {"Name": "QueueName", "Value": {"Fn::GetAtt": [dead_letter_id, "QueueName"]}}
    ]
    assert alarm["Period"] == 300
    assert alarm["EvaluationPeriods"] == 1
    assert alarm["Threshold"] == 1
    assert alarm["ComparisonOperator"] == "GreaterThanOrEqualToThreshold"
    assert alarm["TreatMissingData"] == "notBreaching"
    assert "AlarmActions" not in alarm  # no alarm topic exists in these stacks yet


def test_nat_network_out_alarm_watches_every_fck_nat_group():
    network = TEMPLATES["network"]
    alarm = _alarm(network, "policy-atlas-v3-nat-network-out")
    nat_groups = {
        logical_id
        for logical_id, _ in _resources(network, "AWS::AutoScaling::AutoScalingGroup")
        if "FckNat" in logical_id
    }
    assert nat_groups
    (expression,) = [metric for metric in alarm["Metrics"] if "Expression" in metric]
    assert expression["Expression"].startswith("MAX([")
    stats = [metric["MetricStat"] for metric in alarm["Metrics"] if "MetricStat" in metric]
    assert {stat["Metric"]["Dimensions"][0]["Value"]["Ref"] for stat in stats} == nat_groups
    assert all(stat["Metric"]["Namespace"] == "AWS/EC2" for stat in stats)
    assert all(stat["Metric"]["MetricName"] == "NetworkOut" for stat in stats)
    assert all(stat["Stat"] == "Sum" and stat["Period"] == 300 for stat in stats)
    assert alarm["Threshold"] == 1_000_000_000
    assert alarm["EvaluationPeriods"] == 3
    assert alarm["ComparisonOperator"] == "GreaterThanThreshold"
    assert "AlarmActions" not in alarm


def test_writer_cpu_credit_balance_alarm():
    alarm = _alarm(TEMPLATES["database"], "policy-atlas-v3-db-writer-cpu-credits")
    assert alarm["Namespace"] == "AWS/RDS"
    assert alarm["MetricName"] == "CPUCreditBalance"
    assert alarm["Dimensions"] == [
        {"Name": "DBInstanceIdentifier", "Value": "policy-atlas-v3-db-writer"}
    ]
    assert alarm["Statistic"] == "Minimum"
    assert alarm["Period"] == 300
    assert alarm["Threshold"] == 50
    assert alarm["ComparisonOperator"] == "LessThanThreshold"
    assert "AlarmActions" not in alarm
    # The alarm names the instance the database stack actually creates.
    (instance,) = [
        resource["Properties"]
        for _, resource in _resources(TEMPLATES["database"], "AWS::RDS::DBInstance")
        if resource["Properties"].get("DBInstanceIdentifier") == "policy-atlas-v3-db-writer"
    ]
    assert instance
