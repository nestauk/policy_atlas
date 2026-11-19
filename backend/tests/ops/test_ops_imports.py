"""The production image need not install Cognito typing stubs."""

from __future__ import annotations

import subprocess
import sys


def test_commands_and_environment_import_without_cognito_type_stubs() -> None:
    """Runtime imports succeed when the type-only package is unavailable."""
    code = """
import sys
sys.modules['mypy_boto3_cognito_idp'] = None
sys.modules['mypy_boto3_cognito_idp.client'] = None
sys.modules['mypy_boto3_cognito_idp.type_defs'] = None
import policy_atlas.ops.commands
import policy_atlas.ops.environment
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
