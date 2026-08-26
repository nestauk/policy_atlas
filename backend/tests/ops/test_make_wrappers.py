"""The make wrappers assemble argv the real ops parser accepts — drift fails here.

The per-command make targets (`make user-create ENV=... EMAIL=...`) exist for
operator ergonomics (owner request, 2026-08-25). Their standing risk is drift:
the Makefile maps variable names to flag names by hand, and nothing else would
notice a CLI flag rename until an operator hit it. This suite closes that
seam: every target is dry-run through `scripts/ops_run.sh` (OPS_DRY_RUN=1
prints the exact argv instead of touching AWS or a database), and the printed
argv is fed to the CLI's own ``build_parser()``. A wrapper that assembles an
invocation the parser refuses goes red inside ``make verify``.

Deliberately NOT tested here: the AWS/tunnel setup path of ops_run.sh (needs
live AWS; covered by the runbook), and make-side re-validation of the CLI's
grammar — the mutually-exclusive pairs are forwarded as given precisely so the
parser stays the sole authority, which the both-given case pins.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from policy_atlas.ops.cli import build_parser

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _dry_run(target: str, **variables: str) -> list[str]:
    """Run one make wrapper in dry-run mode and return the argv it assembled.

    Inside ``make verify`` this test's subprocess inherits ``MAKEFLAGS`` from
    the outer make, and GNU make then writes ``make[3]: Entering directory``
    notices into stdout — which this helper would happily parse as CLI argv
    (found by CI, not locally: a bare shell has no outer make). Scrub the
    inherited make variables, pass ``--no-print-directory`` anyway, and refuse
    any surviving make chatter loudly rather than letting it reach the parser.
    """
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL")
    }
    result = subprocess.run(
        [
            "make",
            "-s",
            "--no-print-directory",
            target,
            *(f"{name}={value}" for name, value in variables.items()),
        ],
        cwd=_REPO_ROOT,
        env={**env, "OPS_DRY_RUN": "1"},
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.splitlines()
    polluted = [line for line in lines if line.startswith("make")]
    assert not polluted, f"make chatter leaked into the parsed argv: {polluted}"
    return lines


def test_every_wrapper_assembles_argv_the_real_parser_accepts() -> None:
    parser = build_parser()
    cases = {
        "org-create": dict(ENV="staging", NAME="An Org"),
        "user-create": dict(ENV="staging", EMAIL="a@b.org", NAME="A Name", ORG="An Org"),
        "user-enrol": dict(ENV="prod", EMAIL="a@b.org", NAME="A Name", ORG="An Org"),
        "user-resync": dict(ENV="staging", EMAIL="a@b.org"),
        "user-de-enrol": dict(ENV="staging", SUB="sub-1234"),
        "rows-assign": dict(
            ENV="staging", PORTFOLIO="1cf9db6a-1111-4222-8333-444455556666", ORG="An Org"
        ),
        "admin-grant": dict(ENV="staging", EMAIL="a@b.org"),
        "admin-revoke": dict(ENV="prod", SUB="sub-1234"),
    }
    for target, variables in cases.items():
        argv = _dry_run(target, **variables)
        args = parser.parse_args(argv)  # SystemExit here == wrapper↔CLI drift
        assert args.env == variables["ENV"]


def test_the_wrapper_argv_passes_through_the_parsers_own_normalisation() -> None:
    argv = _dry_run(
        "user-create", ENV="staging", EMAIL="Name@Example.org", NAME="A Name", ORG="Org"
    )
    args = build_parser().parse_args(argv)
    assert args.email == "name@example.org"
    assert args.display_name == "A Name"


def test_exclusive_pairs_are_forwarded_as_given_so_the_cli_owns_the_refusal() -> None:
    argv = _dry_run("admin-grant", ENV="staging", EMAIL="a@b.org", SUB="sub-1234")
    with pytest.raises(SystemExit):
        build_parser().parse_args(argv)


def test_the_operator_annotation_rides_every_wrapper() -> None:
    argv = _dry_run("admin-revoke", ENV="staging", SUB="sub-1234", OPERATOR="ticket-9")
    args = build_parser().parse_args(argv)
    assert args.operator == "ticket-9"


def test_a_missing_required_variable_is_a_make_error_before_anything_runs() -> None:
    result = subprocess.run(
        ["make", "-s", "user-create", "ENV=staging"],
        cwd=_REPO_ROOT,
        env={**os.environ, "OPS_DRY_RUN": "1"},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "EMAIL" in result.stderr


def test_no_wrapper_carries_a_credential_shaped_variable() -> None:
    makefile = (_REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    wrapper_block = makefile[makefile.index("ops-require =") :]
    wrapper_block = wrapper_block[: wrapper_block.index("\ndev:")]
    recipe_lines = [line for line in wrapper_block.splitlines() if line.startswith("\t")]
    assert len(recipe_lines) == 8  # one forwarding line per wrapper, nothing else
    for line in recipe_lines:
        for word in ("PASSWORD", "SECRET", "TOKEN", "DATABASE_URL", "database-url"):
            assert word not in line
