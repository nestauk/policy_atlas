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
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "LOG_LEVEL",
    "LOG_FORMAT",
    "LANGFUSE_TRACING_ENVIRONMENT",
    "POLICY_ATLAS_MODEL_ROUTE",
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
    assert environment["DB_POOL_SIZE"] == "15"
    assert environment["DB_MAX_OVERFLOW"] == "10"
    assert environment["LOG_LEVEL"] == "INFO"
    assert environment["LOG_FORMAT"] == "json"
    assert environment["LANGFUSE_TRACING_ENVIRONMENT"] == "staging"
    assert environment["POLICY_ATLAS_MODEL_ROUTE"] == "openai-direct"


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


def test_bedrock_route_adds_only_the_bedrock_key_from_the_app_secret():
    """Task 053: a Bedrock route passes AWS_BEARER_TOKEN_BEDROCK; OpenAI direct does not."""
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
    assert container["Command"] == ["alembic", "upgrade", "head"]
    secrets = _secret_map(container)
    assert set(secrets) == {"DATABASE_URL"}
    assert "db_connection_string" in json.dumps(secrets["DATABASE_URL"])

    services = _resources(TEMPLATES["app"], "AWS::ECS::Service")
    assert len(services) == 1
    assert services[0][1]["Properties"]["DesiredCount"] == 0


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
