"""Pin: operator-only distributions stay out of the request path's import graph.

Task 033 put `boto3` and its type stubs in a **non-default** dependency group
(`pyproject.toml` `[dependency-groups] ops`) that the Dockerfile installs without,
and this file pinned that the API process never imports them.

Task 045 (approved dependency gate) moved `boto3` itself into the main dependencies:
the Cohere embedding backend and the Claude search-generation backend under `core/`
and `evidence_search/` call Amazon Bedrock through it, so the deployed image now
ships the SDK. What the image still does not ship is the **type stubs**
(`boto3-stubs[...]`, importable as `mypy_boto3_*`), which remain in `ops`. A
runtime `from mypy_boto3_... import ...` under `api/` or `core/` would make the API
process unable to start on an image built to spec, whatever the Dockerfile says —
and it is exactly the import a helper reaches for when it wants a typed client.
Stubs belong under `TYPE_CHECKING` in request-path code; `ops/` may import them for
real because it runs where they are installed.

Structural on purpose: the behavioural version is "build the image and start the
app", which is exactly the check that has not always been available (a Docker
daemon with registry egress).
"""

import ast
from pathlib import Path
from types import ModuleType

import policy_atlas.api
import policy_atlas.core
import policy_atlas.ops

#: Distributions the request path must not reach at runtime, by top-level module
#: name: the boto3 type stubs, which stay in the `ops` group (task 045).
_FORBIDDEN = ("mypy_boto3_cognito_idp", "mypy_boto3_bedrock_runtime")


def _imported_modules(package: ModuleType) -> dict[str, set[str]]:
    """Map each module in a package to the top-level module names it imports.

    Args:
        package: An imported package whose `__file__` locates its directory.

    Returns:
        Relative module path -> the set of root module names it imports.
    """
    root = Path(package.__file__ or "").parent
    imported: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*.py")):
        roots: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots.add(node.module.split(".")[0])
        imported[str(path.relative_to(root))] = roots
    return imported


def test_no_module_under_the_api_or_core_imports_the_aws_sdk_stubs() -> None:
    """`api/` and `core/` must import nothing the deployed image does not ship."""
    offenders = {
        f"{package.__name__}/{module}": sorted(roots & set(_FORBIDDEN))
        for package in (policy_atlas.api, policy_atlas.core)
        for module, roots in _imported_modules(package).items()
        if roots & set(_FORBIDDEN)
    }

    assert offenders == {}


def test_the_operator_cli_is_where_the_aws_sdk_stubs_live() -> None:
    """The control that keeps the assertion above from passing vacuously.

    If the stubs left the codebase entirely — or moved behind `TYPE_CHECKING`
    everywhere — the check above would keep passing while proving nothing about
    the boundary. It is a real boundary: `ops/` imports the stubs for real,
    `api/` and `core/` do not, and only `ops/` runs where they are installed.
    """
    importers = {
        module
        for module, roots in _imported_modules(policy_atlas.ops).items()
        if roots & set(_FORBIDDEN)
    }

    assert importers
