"""Pin: the AWS SDK stays out of the request path's import graph (task 033).

`boto3` and `boto3-stubs` are a **non-default** dependency group (`pyproject.toml`
`[dependency-groups] ops`), and the Dockerfile installs without it, so the
deployed image carries no AWS SDK at all. That is checked at the image — and the
image check needs a Docker daemon with registry egress, which the build
environment has not always had (`verification.md` § Known unverified).

This is the same property asserted where it cannot go unchecked: at the import
graph. A single `import boto3` anywhere under `api/` or `core/` makes the API
process unable to start on an image built to spec, whatever the Dockerfile says
— and it is the kind of import that arrives innocently, when a helper wants one
small thing from the operator's world. The operator CLI (`ops/`) is where the
SDK belongs and is not run from the image.

Structural on purpose: the behavioural version is "build the image and start the
app", which is exactly the check that was unavailable.
"""

import ast
from pathlib import Path
from types import ModuleType

import policy_atlas.api
import policy_atlas.core
import policy_atlas.ops

#: Distributions the request path must not reach, by top-level module name.
_FORBIDDEN = ("boto3", "botocore")


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


def test_no_module_under_the_api_or_core_imports_the_aws_sdk() -> None:
    """`api/` and `core/` must import nothing the deployed image does not ship."""
    offenders = {
        f"{package.__name__}/{module}": sorted(roots & set(_FORBIDDEN))
        for package in (policy_atlas.api, policy_atlas.core)
        for module, roots in _imported_modules(package).items()
        if roots & set(_FORBIDDEN)
    }

    assert offenders == {}


def test_the_operator_cli_is_where_the_aws_sdk_lives() -> None:
    """The control that keeps the assertion above from passing vacuously.

    If `boto3` left the codebase entirely — or moved behind a lazy import
    everywhere — the check above would keep passing while proving nothing about
    the boundary. It is a real boundary: `ops/` imports the SDK, `api/` and
    `core/` do not, and only `ops/` runs where the SDK is installed.
    """
    importers = {
        module
        for module, roots in _imported_modules(policy_atlas.ops).items()
        if roots & set(_FORBIDDEN)
    }

    assert importers
