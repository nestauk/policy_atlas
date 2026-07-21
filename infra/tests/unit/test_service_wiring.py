"""Assertions for the Policy Atlas API and migration task wiring."""
import json

from tests.unit.test_synth import TEMPLATES, _resources


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
}
APP_SECRET_NAMES = {
    "OPENAI_API_KEY",
    "OPENALEX_EMAIL",
    "OPENALEX_API_KEY",
    "OVERTON_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
}


def _task_definition(family: str) -> dict:
    """Return the synthesized ECS task definition having ``family``."""
    return next(
        resource["Properties"]
        for _, resource in _resources(TEMPLATES["app"], "AWS::ECS::TaskDefinition")
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
    api_container = _container(_task_definition("policy-atlas-v3-api"))
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


def test_api_container_references_database_and_app_secrets_without_values():
    secrets = _secret_map(_container(_task_definition("policy-atlas-v3-api")))
    assert set(secrets) == {"DATABASE_URL", *APP_SECRET_NAMES}

    database_reference = json.dumps(secrets["DATABASE_URL"])
    assert "db_connection_string" in database_reference
    for name in APP_SECRET_NAMES:
        reference = json.dumps(secrets[name])
        assert name in reference
        assert "policy_atlas_v3/app" in reference

    # ECS Secret ValueFrom entries are Secrets Manager ARNs/dynamic references;
    # none is an injected credential value in the synthesized template.
    assert all(isinstance(reference, (str, dict)) for reference in secrets.values())


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
