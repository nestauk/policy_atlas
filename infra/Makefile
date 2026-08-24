.PHONY: setup test

setup:
	@test -d .venv || uv venv .venv
	@mkdir -p "$${TMPDIR:-/tmp}/policy-atlas-uv-cache"
	UV_CACHE_DIR="$${TMPDIR:-/tmp}/policy-atlas-uv-cache" uv pip install --python .venv/bin/python -r requirements.txt

test: setup
	@mkdir -p "$${TMPDIR:-/tmp}/policy-atlas-uv-cache"
	UV_CACHE_DIR="$${TMPDIR:-/tmp}/policy-atlas-uv-cache" uv pip install --python .venv/bin/python -r requirements-dev.txt
	@mkdir -p "$${TMPDIR:-/tmp}/policy-atlas-jsii-cache"
	CDK_DEFAULT_ACCOUNT=111111111111 JSII_RUNTIME_PACKAGE_CACHE="$${TMPDIR:-/tmp}/policy-atlas-jsii-cache" JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 .venv/bin/python -m pytest tests/ -q
