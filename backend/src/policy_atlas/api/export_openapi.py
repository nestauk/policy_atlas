"""OpenAPI export for the Policy Atlas API — the single schema-first source of truth.

Builds the FastAPI application's OpenAPI document without touching any real
environment or external dependency: no database connection, no live JWKS
fetch, no network at all. `app.openapi()` only introspects routes and
Pydantic models — it never runs the app's `lifespan` (that only executes
under `TestClient`/uvicorn, never for a bare `.openapi()` call), so a
synthetic, connection-free `Settings` is enough to build the app.

`StreamingResponse` (the SSE endpoint) and a discriminated-union request
body don't fully advertise their component vocabulary through FastAPI's
normal route introspection, so this module explicitly folds the `SseFrame`
and `CheckInResponse` discriminated unions' JSON Schemas into
`components.schemas`, keyed by model name — the generated TypeScript client
narrows on `type`/`kind` for every frame and response variant as a result.

Output is deterministic (sorted keys, stable formatting) so `make
drift-check` produces a meaningful diff when the backend contract changes
without a matching regeneration of the committed frontend artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from policy_atlas.api.app import create_app
from policy_atlas.api.contract.check_ins import CheckInResponse
from policy_atlas.api.contract.sse import SseFrame
from policy_atlas.api.dev_issuer import init
from policy_atlas.api.settings import Settings

#: Discriminated unions that need an explicit named-component fold: neither
#: is fully advertised by FastAPI's own route introspection (SSE is a
#: `StreamingResponse` with no declared body schema; the check-in response
#: union is a request body, but folding it here keeps both unions on the
#: same explicit, reviewable path rather than depending on FastAPI's
#: incidental component naming).
_NAMED_UNIONS: tuple[tuple[str, Any], ...] = (
    ("SseFrame", SseFrame),
    ("CheckInResponse", CheckInResponse),
)


def build_settings(tmp_dir: Path) -> Settings:
    """Build a synthetic, connection-free `Settings` for schema export.

    Args:
        tmp_dir: Scratch directory for a throwaway development-issuer JWKS.
            Nothing under it is ever read at request time — the JWKS path
            only needs to exist for `Settings` construction.

    Returns:
        Settings sufficient to construct the app and build its OpenAPI
        document. `database_url` is a placeholder: schema export never
        opens a connection.
    """
    key_dir = tmp_dir / "openapi-export-issuer"
    return Settings(
        oidc_issuer="http://dev-issuer.local",
        oidc_client_id="openapi-export",
        oidc_jwks_url=None,
        oidc_jwks_path=init(key_dir),
        app_origin="http://app.example.test",
        database_url="postgresql+psycopg://unused/unused",
    )


def build_openapi_schema() -> dict[str, Any]:
    """Build the app's OpenAPI document, with SSE/check-in unions folded in.

    Returns:
        The full OpenAPI schema dict, safe to serialize.
    """
    with tempfile.TemporaryDirectory() as tmp:
        settings = build_settings(Path(tmp))
        app = create_app(settings=settings)
        schema = app.openapi()
    _fold_named_unions(schema)
    return schema


def _fold_named_unions(schema: dict[str, Any]) -> None:
    """Merge named discriminated-union component schemas in place.

    Args:
        schema: The OpenAPI document, mutated in place. Each entry in
            `_NAMED_UNIONS` contributes its member models' schemas (via
            their pydantic `$defs`) plus the union itself, keyed by name.
    """
    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    for name, union_type in _NAMED_UNIONS:
        union_schema = TypeAdapter(union_type).json_schema(
            ref_template="#/components/schemas/{model}"
        )
        defs = union_schema.pop("$defs", {})
        schemas.update(defs)
        schemas[name] = union_schema


def export(out_path: Path) -> None:
    """Write the deterministic OpenAPI document to `out_path`.

    Args:
        out_path: Destination file. Parent directories are created as
            needed.
    """
    schema = build_openapi_schema()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(schema, sort_keys=True, indent=2, separators=(",", ": ")) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the OpenAPI export command-line interface.

    Args:
        argv: Optional command-line arguments excluding the program name.

    Returns:
        Process exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_path", type=Path, help="Destination path for the OpenAPI JSON.")
    args = parser.parse_args(argv)
    export(args.out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
