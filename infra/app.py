#!/usr/bin/env python3
import os
import json
import aws_cdk as cdk
from aws_cdk import Environment

from infra.database_stack import DatabaseStack
from infra.cert_stack import PaV3CertStack
from infra.policy_atlas_stack import PolicyAtlasStack
from infra.network_stack import NetworkStack

# Create CDK application instance,
# and pull env_name from provided context. No default; if missing, abort.
app = cdk.App()

env_name = app.node.try_get_context("env_name")
if not env_name:
    raise ValueError("Context variable 'env_name' is required. Please provide it using '-c env_name=your_env'.")

# Stage guard: 'network' deploys only the network stack (first deploy, before a
# VPC exists for Vpc.from_lookup to find); 'all' (default) deploys every stack.
stage = app.node.try_get_context("stage") or "all"
if stage not in ("network", "all"):
    raise ValueError(f"Context variable 'stage' must be 'network' or 'all', got '{stage}'. Please provide it using '-c stage=network|all'.")

# Account is never committed to config; it comes from the environment so the
# same config JSONs work across accounts without an aws_account_id key.
account = os.environ.get("CDK_DEFAULT_ACCOUNT")
if not account:
    raise ValueError("Environment variable 'CDK_DEFAULT_ACCOUNT' is required. Please set it before running cdk synth/deploy.")

with open('network_config.json') as f:
    config = json.load(f)
    network_config = config.get(env_name)
    if not network_config:
        raise ValueError(f"No network configuration found for environment '{env_name}' in network_config.json.")

with open('pa_config.json') as f:
    config = json.load(f)
    pa_config = config.get(env_name)
    if not pa_config:
        raise ValueError(f"No configuration found for environment '{env_name}' in pa_config.json.")

with open('db_config.json') as f:
    config = json.load(f)
    db_config = config.get(env_name)
    if not db_config:
        raise ValueError(f"No database configuration found for environment '{env_name}' in db_config.json.")

# Add 'VPCManaged': true tag to all resources recursively.
# Just in case we're looking manually and need to spot what this has built.
cdk.Tags.of(app).add("VPCManaged", "true", apply_to_launched_instances=True)

# Why separate stacks?
# CDK will pick up on changes needed independently - so if
# we need to push Policy Atlas or Database updates independently, we can.
# The network stack will likely never need to change, but it's separate anyway for dependency.
net_env = Environment(
    account=account,
    region=network_config['aws_region']
)

NetworkStack(app, "PaV3NetworkStack", network_config=network_config, env=net_env,
             aws_region=network_config['aws_region'], env_name=env_name)

if stage == "all":
    cert_env = Environment(
        account=account,
        region="us-east-1",
    )

    cert_stack = PaV3CertStack(
        app,
        "PaV3CertStack",
        network_config=network_config,
        env=cert_env,
        cross_region_references=True,
    )

    db_env = Environment(
        account=account,
        region=db_config['aws_region']
    )

    DatabaseStack(app, "PaV3DatabaseStack", db_config=db_config, env=db_env, env_name=env_name)

    pa_env = Environment(
        account=account,
        region=pa_config['aws_region']
    )

    PolicyAtlasStack(
        app,
        "PaV3AppStack",
        pa_config=pa_config,
        certificate=cert_stack.certificate,
        env=pa_env,
        env_name=env_name,
        cross_region_references=True,
    )

app.synth()
