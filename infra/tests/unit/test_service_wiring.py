"""Assertions for the Policy Atlas API and migration task wiring."""
import json
import tomllib
from pathlib import Path

from tests.unit.test_synth import BEDROCK_APP_TEMPLATE, OPENAI_APP_TEMPLATE, TEMPLATES, _resources

REPO_ROOT = Path(__file__).resolve().parents[3]


API_ENVIRONMENT_NAMES = {
    "OIDC_ISSUER",
    "OIDC_JWKS_URL",
    "OIDC_CLIENT_ID",
    "APP_ORIGIN",
    "PA_BACKEND_MODE",
    "RUN_EXECUTOR_MAX",
    "RUNS_PER_USER",
    "TASK_QUOTA_PER_YEAR",
    "FORWARDED_ALLOW_IPS",
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "LOG_LEVEL",
    "LOG_FORMAT",
    "LANGFUSE_TRACING_ENVIRONMENT",
    "POLICY_ATLAS_MODEL_ROUTE",
    "POLICY_ATLAS_UPLOAD_BUCKET",
    "POLICY_ATLAS_THEORY_OF_CHANGE",
    "POLICY_ATLAS_INGEST_MODE",
    "POLICY_ATLAS_INGEST_QUEUE_URL",
}
APP_SECRET_NAMES = {
    "OPENAI_API_KEY",
    "OPENALEX_EMAIL",
    "OPENALEX_API_KEY",
    "OVERTON_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
}
OPS_ENVIRONMENT_NAMES = {
    "OIDC_ISSUER", "OIDC_JWKS_URL", "OIDC_CLIENT_ID", "APP_ORIGIN",
    "POLICY_ATLAS_SERVICE_ROLE", "POLICY_ATLAS_SELF_SIGNUP",
    "POLICY_ATLAS_SELF_SIGNUP_MAX_PER_HOUR", "OPS_UI_DIR",
    "OPS_CONTENT_SECURITY_POLICY", "OPS_CSP_MODE",
    "RUNS_PER_USER", "TASK_QUOTA_PER_YEAR", "DB_POOL_SIZE", "DB_MAX_OVERFLOW",
    "FORWARDED_ALLOW_IPS", "LOG_LEVEL", "LOG_FORMAT", "PA_BACKEND_MODE",
}


def _task_definition(family: str, template: dict | None = None) -> dict:
    """Return the synthesized ECS task definition having ``family``."""
    return next(
        resource["Properties"]
        for _, resource in _resources(template or TEMPLATES["app"], "AWS::ECS::TaskDefinition")
        if resource["Properties"]["Family"] == family
    )


def _container(task_definition: dict) -> dict:
    """Return the only application container in a task definition."""
    containers = task_definition["ContainerDefinitions"]
    assert len(containers) == 1
    return containers[0]


def _secret_map(container: dict) -> dict[str, object]:
    """Map synthesized ECS secret environment names to their references."""
    return {secret["Name"]: secret["ValueFrom"] for secret in container["Secrets"]}


def test_api_container_has_the_complete_deployed_plain_environment_map():
    api_container = _container(_task_definition("policy-atlas-v3-api", OPENAI_APP_TEMPLATE))
    environment = {
        item["Name"]: item["Value"] for item in api_container["Environment"]
    }
    assert set(environment) == API_ENVIRONMENT_NAMES
    assert environment["APP_ORIGIN"] == "https://v3.policyatlas.uk"
    assert environment["PA_BACKEND_MODE"] == "live"
    assert environment["RUN_EXECUTOR_MAX"] == "10"
    assert environment["RUNS_PER_USER"] == "3"
    assert environment["TASK_QUOTA_PER_YEAR"] == "50"
    assert environment["FORWARDED_ALLOW_IPS"] == "1.2.3.4/5"
    assert environment["DB_POOL_SIZE"] == "15"
    assert environment["DB_MAX_OVERFLOW"] == "10"
    assert environment["LOG_LEVEL"] == "INFO"
    assert environment["LOG_FORMAT"] == "json"
    assert environment["LANGFUSE_TRACING_ENVIRONMENT"] == "staging"
    assert environment["POLICY_ATLAS_MODEL_ROUTE"] == "openai-direct"
    assert environment["POLICY_ATLAS_INGEST_MODE"] == "queued"
    assert "IngestQueue" in json.dumps(environment["POLICY_ATLAS_INGEST_QUEUE_URL"])
    assert environment["POLICY_ATLAS_UPLOAD_BUCKET"] == {"Ref": _uploads_bucket_id()}
    assert environment["POLICY_ATLAS_THEORY_OF_CHANGE"] == "1"


def test_theory_of_change_is_on_in_staging_only():
    """Colleagues try it on staging; production stays off."""
    config = json.loads((REPO_ROOT / "infra/pa_config.json").read_text())
    backends = {env: config[env]["policy_atlas_config"]["backend"] for env in config}
    assert {env: backend.get("theory_of_change") for env, backend in backends.items()} == {
        "staging": True,
        "prod": False,
    }


def _uploads_bucket_id(template: dict | None = None) -> str:
    """The logical id of the uploads bucket."""
    return next(
        name
        for name, resource in _resources(template or TEMPLATES["app"], "AWS::S3::Bucket")
        if resource["Properties"].get("BucketName") == "policy-atlas-v3-staging-uploads"
    )


def test_the_uploads_bucket_is_private_encrypted_https_only_and_retained():
    template = TEMPLATES["app"]
    bucket_id = _uploads_bucket_id()
    bucket = template["Resources"][bucket_id]
    assert bucket["DeletionPolicy"] == "Retain" and bucket["UpdateReplacePolicy"] == "Retain"
    properties = bucket["Properties"]
    assert properties["PublicAccessBlockConfiguration"] == {
        "BlockPublicAcls": True,
        "BlockPublicPolicy": True,
        "IgnorePublicAcls": True,
        "RestrictPublicBuckets": True,
    }
    rules = properties["BucketEncryption"]["ServerSideEncryptionConfiguration"]
    assert rules[0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"
    assert "VersioningConfiguration" not in properties
    # A bucket policy refuses any request that is not over HTTPS.
    policy = next(
        resource["Properties"]["PolicyDocument"]["Statement"]
        for _, resource in _resources(template, "AWS::S3::BucketPolicy")
        if resource["Properties"]["Bucket"] == {"Ref": bucket_id}
    )
    assert any(
        statement["Effect"] == "Deny"
        and statement["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}
        for statement in policy
    )


def test_only_the_api_task_role_may_use_the_uploads_bucket_under_tasks():
    template = TEMPLATES["app"]
    bucket_id = _uploads_bucket_id()
    granted = [
        resource
        for _, resource in _resources(template, "AWS::IAM::Policy")
        if bucket_id in str(resource["Properties"]["PolicyDocument"])
    ]
    assert len(granted) == 1
    roles = granted[0]["Properties"]["Roles"]
    api = _task_definition("policy-atlas-v3-api")
    role_id = api["TaskRoleArn"]["Fn::GetAtt"][0]
    assert roles == [{"Ref": role_id}]
    statements = granted[0]["Properties"]["PolicyDocument"]["Statement"]
    objects = [s for s in statements if "s3:PutObject" in s["Action"]]
    assert objects and all("/tasks/*" in str(s["Resource"]) for s in objects)


def test_api_container_references_database_and_app_secrets_without_values():
    secrets = _secret_map(_container(_task_definition("policy-atlas-v3-api", OPENAI_APP_TEMPLATE)))
    assert set(secrets) == {"DATABASE_URL", *APP_SECRET_NAMES}

    database_reference = json.dumps(secrets["DATABASE_URL"])
    assert "db_connection_string" in database_reference
    for name in APP_SECRET_NAMES:
        reference = json.dumps(secrets[name])
        assert name in reference
        assert "policy_atlas_v3/app" in reference

    # ECS Secret ValueFrom entries must be Secrets Manager references (an ARN
    # string or an Fn:: structure that mentions the secret), never an inlined
    # literal value.
    for reference in secrets.values():
        rendered = json.dumps(reference)
        assert "secretsmanager" in rendered or "Fn::" in rendered or "Ref" in rendered


def test_ops_container_has_the_complete_least_privilege_environment_and_secret_map():
    container = _container(_task_definition("policy-atlas-v3-ops"))
    environment = {item["Name"]: item["Value"] for item in container["Environment"]}
    assert set(environment) == OPS_ENVIRONMENT_NAMES
    assert environment == {
        "OIDC_ISSUER": environment["OIDC_ISSUER"],
        "OIDC_JWKS_URL": environment["OIDC_JWKS_URL"],
        "OIDC_CLIENT_ID": environment["OIDC_CLIENT_ID"],
        "APP_ORIGIN": "https://ops.v3.policyatlas.uk",
        "POLICY_ATLAS_SERVICE_ROLE": "ops",
        "POLICY_ATLAS_SELF_SIGNUP": "0",
        "POLICY_ATLAS_SELF_SIGNUP_MAX_PER_HOUR": "100",
        "OPS_UI_DIR": "/app/ops-ui",
        # No API origin and no CAPTCHA hosts: the ops pages call only their
        # own host and the sign-in service.
        "OPS_CONTENT_SECURITY_POLICY": (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self'; "
            "connect-src 'self' https://cognito-idp.eu-west-2.amazonaws.com "
            "https://policy-atlas-v3.auth.eu-west-2.amazoncognito.com "
            "https://auth.v3.policyatlas.uk; "
            "frame-src 'self' https://policy-atlas-v3.auth.eu-west-2.amazoncognito.com "
            "https://auth.v3.policyatlas.uk; "
            "frame-ancestors 'none'; form-action 'self'; object-src 'none'; base-uri 'self'"
        ),
        "OPS_CSP_MODE": "enforce",
        "RUNS_PER_USER": "3",
        "TASK_QUOTA_PER_YEAR": "50",
        "DB_POOL_SIZE": "5",
        "DB_MAX_OVERFLOW": "5",
        "FORWARDED_ALLOW_IPS": "1.2.3.4/5",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "json",
        "PA_BACKEND_MODE": "stub",
    }
    secrets = _secret_map(container)
    assert set(secrets) == {"DATABASE_URL"}
    assert "OpsDbSecret" in json.dumps(secrets["DATABASE_URL"])
    assert "db_connection_string" in json.dumps(secrets["DATABASE_URL"])


def test_ops_and_api_task_roles_hold_only_their_expected_cognito_permissions():
    policies = _resources(TEMPLATES["app"], "AWS::IAM::Policy")
    api_role = _task_definition("policy-atlas-v3-api")["TaskRoleArn"]["Fn::GetAtt"][0]
    ops_role = _task_definition("policy-atlas-v3-ops")["TaskRoleArn"]["Fn::GetAtt"][0]
    api_actions = []
    ops_actions = []
    for _, policy in policies:
        roles = policy["Properties"]["Roles"]
        # CloudFormation writes one action as a plain string, several as a list.
        all_actions = [
            action
            for statement in policy["Properties"]["PolicyDocument"]["Statement"]
            for action in (
                [statement["Action"]] if isinstance(statement["Action"], str) else statement["Action"]
            )
        ]
        assert "*" not in all_actions and "cognito-idp:*" not in all_actions
        actions = [action for action in all_actions if action.startswith("cognito-idp:")]
        if {"Ref": api_role} in roles:
            api_actions.extend(actions)
        if {"Ref": ops_role} in roles:
            ops_actions.extend(actions)
            for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
                if any(str(a).startswith("cognito-idp:") for a in (
                    [statement["Action"]] if isinstance(statement["Action"], str) else statement["Action"]
                )):
                    # Scoped to the pool, never a wildcard resource.
                    assert "Arn" in json.dumps(statement["Resource"]) and "UserPool" in json.dumps(statement["Resource"])
                    assert statement["Resource"] != "*"
    assert not api_actions
    assert sorted(ops_actions) == sorted([
        "cognito-idp:AdminCreateUser", "cognito-idp:AdminGetUser",
        "cognito-idp:ListUsers", "cognito-idp:AdminDisableUser",
        "cognito-idp:AdminUserGlobalSignOut", "cognito-idp:AdminEnableUser",
    ])


def test_bedrock_route_adds_only_the_bedrock_key_from_the_app_secret():
    """A Bedrock route passes AWS_BEARER_TOKEN_BEDROCK; OpenAI direct does not."""
    container = _container(_task_definition("policy-atlas-v3-api", BEDROCK_APP_TEMPLATE))
    environment = {item["Name"]: item["Value"] for item in container["Environment"]}
    assert environment["POLICY_ATLAS_MODEL_ROUTE"] == "bedrock"
    secrets = _secret_map(container)
    assert set(secrets) == {"DATABASE_URL", *APP_SECRET_NAMES, "AWS_BEARER_TOKEN_BEDROCK"}
    reference = json.dumps(secrets["AWS_BEARER_TOKEN_BEDROCK"])
    assert "AWS_BEARER_TOKEN_BEDROCK" in reference
    assert "policy_atlas_v3/app" in reference


def test_every_configured_model_route_exists_in_the_backend_route_file():
    """A typo in pa_config.json fails here, not as a backend crash after deploy."""
    routes = tomllib.loads(
        (REPO_ROOT / "backend/src/policy_atlas/model_routes.toml").read_text()
    )["routes"]
    config = json.loads((REPO_ROOT / "infra/pa_config.json").read_text())
    for env_name, env_config in config.items():
        route = env_config["policy_atlas_config"]["backend"]["model_route"]
        assert route in routes, f"{env_name}: unknown model route {route!r}"


def test_migration_task_is_one_shot_and_has_only_the_database_secret():
    migration = _task_definition("policy-atlas-v3-migrate")
    assert migration["Cpu"] == "512"
    assert migration["Memory"] == "1024"

    container = _container(migration)
    assert container["Command"][:2] == ["sh", "-c"]
    assert container["Command"][2].startswith("alembic upgrade head && (python -m policy_atlas.ops.db_role sync || echo")
    assert [item["Name"] for item in container["Environment"]] == ["OPS_DB_SECRET_ARN"]
    assert "OpsDbSecret" in json.dumps(container["Environment"])
    secrets = _secret_map(container)
    assert set(secrets) == {"DATABASE_URL"}
    assert "db_connection_string" in json.dumps(secrets["DATABASE_URL"])

    services = _resources(TEMPLATES["app"], "AWS::ECS::Service")
    assert len(services) == 2
    assert all(service["Properties"]["DesiredCount"] == 0 for _, service in services)


def test_migration_task_role_can_read_and_update_only_the_ops_database_secret():
    migration_role = _task_definition("policy-atlas-v3-migrate")["TaskRoleArn"]["Fn::GetAtt"][0]
    policies = [
        policy["Properties"]["PolicyDocument"]["Statement"]
        for _, policy in _resources(TEMPLATES["app"], "AWS::IAM::Policy")
        if policy["Properties"]["Roles"] == [{"Ref": migration_role}]
    ]
    actions = {
        action
        for statements in policies
        for statement in statements
        for action in statement["Action"]
        if action.startswith("secretsmanager:")
    }
    assert actions == {"secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"}
    assert all("OpsDbSecret" in json.dumps(statement["Resource"]) for statements in policies for statement in statements)


def test_alb_timeout_and_migration_deploy_export_are_present_without_autoscaling():
    _, alb = _resources(TEMPLATES["network"], "AWS::ElasticLoadBalancingV2::LoadBalancer")[0]
    attributes = alb["Properties"]["LoadBalancerAttributes"]
    assert {item["Key"]: item["Value"] for item in attributes}["idle_timeout.timeout_seconds"] == "120"

    parameter_names = {
        resource["Properties"]["Name"]
        for _, resource in _resources(TEMPLATES["app"], "AWS::SSM::Parameter")
    }
    assert "/policy_atlas_v3/deploy/migration_task_def_arn" in parameter_names

    resource_types = {
        resource["Type"]
        for template in TEMPLATES.values()
        for resource in template["Resources"].values()
    }
    assert not any(name.startswith("AWS::ApplicationAutoScaling::") for name in resource_types)
