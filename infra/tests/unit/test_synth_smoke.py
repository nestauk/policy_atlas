"""A.2 scaffolding smoke test.

Proves the ported CDK app can synth all three A.2 stacks (network, database,
app) without making AWS calls: dummy account, bundling disabled, and the
backend Docker image asset mocked out (backend/Dockerfile lands in A.4, after
this task — the mock only stands in for the not-yet-authored image content,
not for anything infra-side).

This is scaffolding only. The full table-driven suite over the port-map
namespacing table is task A.3.
"""
import json
import os
from pathlib import Path
from unittest.mock import patch

import aws_cdk as cdk
from aws_cdk import Environment, aws_ecs as ecs
from aws_cdk.assertions import Template

from infra.database_stack import DatabaseStack
from infra.network_stack import NetworkStack
from infra.policy_atlas_stack import PolicyAtlasStack

INFRA_ROOT = Path(__file__).resolve().parents[2]
DUMMY_ACCOUNT = "111111111111"
ENV_NAME = "staging"


def _load_config(filename: str) -> dict:
    with open(INFRA_ROOT / filename) as f:
        return json.load(f)[ENV_NAME]


def test_all_a2_stacks_synth_without_aws_calls(monkeypatch):
    monkeypatch.setenv("CDK_DEFAULT_ACCOUNT", DUMMY_ACCOUNT)
    monkeypatch.setenv("JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION", "1")

    network_config = _load_config("network_config.json")
    db_config = _load_config("db_config.json")
    pa_config = _load_config("pa_config.json")

    # Bundling skipped for every stack — no Docker-based asset bundling at
    # synth time (Vpc.from_lookup / HostedZone.from_lookup fall back to CDK's
    # built-in dummy context values, so no AWS lookups happen either).
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    account = os.environ["CDK_DEFAULT_ACCOUNT"]
    env = Environment(account=account, region=network_config["aws_region"])

    network_stack = NetworkStack(
        app, "PaV3NetworkStack",
        network_config=network_config, env=env,
        aws_region=network_config["aws_region"], env_name=ENV_NAME,
    )
    database_stack = DatabaseStack(
        app, "PaV3DatabaseStack",
        db_config=db_config, env=env, env_name=ENV_NAME,
    )

    # The backend container image is built from ../backend, whose Dockerfile
    # is authored in A.4 (after this task). Stand in with a registry image so
    # asset staging doesn't need a real Docker build context yet.
    dummy_image = ecs.ContainerImage.from_registry("public.ecr.aws/docker/library/nginx:stable")
    with patch("aws_cdk.aws_ecs.ContainerImage.from_asset", return_value=dummy_image):
        app_stack = PolicyAtlasStack(
            app, "PaV3AppStack",
            pa_config=pa_config, env=env, env_name=ENV_NAME,
        )

    for stack in (network_stack, database_stack, app_stack):
        template = Template.from_stack(stack)
        assert template.to_json()["Resources"]
