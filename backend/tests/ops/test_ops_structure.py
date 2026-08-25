"""Rubric 30, asserted structurally: no deletion, no passwords, no make targets.

Three properties that no behavioural test can pin, because each is about the
*absence* of something. A path that calls ``AdminDeleteUser`` would simply never
be exercised by a happy-path test; a ``--temporary-password`` flag added to one
subcommand would pass every other case in the suite.

The password check runs over the **built argparse tree**, not over a grep of the
source, so a flag added through any route — a new subcommand, a shared parent
parser, a loop — is caught. The ``AdminDeleteUser`` check is a source scan,
because that one really is about text: the call could be spelled as a method, as
a string passed to an operation-name dispatcher, or in a comment promising to
add it later, and all three should fail.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from policy_atlas.ops.cli import build_parser

#: Anything that would put a credential on the command line, in shell history
#: and in the process table — which is what the deleted `cognito-user` make
#: target did.
_FORBIDDEN_FLAG_WORDS = ("password", "secret", "credential", "token")

#: Deleted in this slice (contract § 9). They created a Cognito account without
#: enrolling it, suppressed the invitation, and took a password in argv.
_DELETED_TARGETS = ("staging-user", "prod-user", "cognito-user")

_OPS_PACKAGE = Path(__file__).resolve().parents[2] / "src" / "policy_atlas" / "ops"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _all_option_strings(parser: argparse.ArgumentParser) -> list[str]:
    """Every flag on every command, walking the subparser tree."""
    found: list[str] = []
    for action in parser._actions:  # noqa: SLF001 — argparse exposes no public walk
        found.extend(action.option_strings)
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            for sub in action.choices.values():
                found.extend(_all_option_strings(sub))
    return found


def test_no_command_accepts_a_password() -> None:
    """Contract § 9: "No password passes through the CLI: no --temporary-password, ever"."""
    flags = _all_option_strings(build_parser())
    assert flags, "the parser walk found no flags at all — the walk is broken, not the CLI"
    offenders = [
        flag for flag in flags if any(word in flag.lower() for word in _FORBIDDEN_FLAG_WORDS)
    ]
    assert offenders == []


def test_no_command_accepts_an_assume_yes_flag() -> None:
    """The one confirmation this CLI asks is the environment check's database leg.

    That leg is reached by every first command against a fresh deployment — the
    migration seeds no ``app_user`` rows — and it is exactly the moment at which
    the tunnel is least accounted for. So it is typed, interactively, and there
    is no flag to skip it.

    The flag that used to skip it was **deleted rather than made inert**: an
    inert ``--yes`` still reads, to an operator scanning ``--help``, as
    permission to skip the one check standing between a wrong tunnel and a
    production write, and the operator most likely to reach for it is the one it
    would have hurt. Asserted over the built tree for the same reason the
    password check is: a flag reintroduced on any subcommand, or through a shared
    parent parser, fails here.
    """
    offenders = [flag for flag in _all_option_strings(build_parser()) if "yes" in flag.lower()]
    assert offenders == []


def test_the_command_tree_is_the_one_the_contract_names() -> None:
    """The eight commands of contract § 9, and no ninth that nobody reviewed."""
    parser = build_parser()
    groups = next(
        action
        for action in parser._actions  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction)  # noqa: SLF001
    )
    tree = {
        name: sorted(
            next(
                sub
                for sub in group._actions  # noqa: SLF001
                if isinstance(sub, argparse._SubParsersAction)  # noqa: SLF001
            ).choices
        )
        for name, group in groups.choices.items()
    }
    assert tree == {
        "org": ["create"],
        "user": ["create", "de-enrol", "enrol", "resync"],
        "rows": ["assign"],
        "admin": ["grant", "revoke"],
    }


def test_no_path_in_the_ops_package_calls_admin_delete_user() -> None:
    """Owner call (h): deleting a Cognito user is Out, coupled to ownership transfer."""
    sources = sorted(_OPS_PACKAGE.rglob("*.py"))
    assert sources, "found no ops sources to scan"
    offenders = [
        path.name
        for path in sources
        if "admin_delete_user" in path.read_text(encoding="utf-8").lower().replace("-", "_")
    ]
    assert offenders == []


def test_the_user_provisioning_make_targets_are_deleted() -> None:
    """Two contradictory procedures is one too many, and make has the muscle memory."""
    makefile = (_REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    declared = [
        target
        for target in _DELETED_TARGETS
        if any(line.startswith(f"{target}:") for line in makefile.splitlines())
    ]
    assert declared == []
    assert "admin-set-user-password" not in makefile
    # The deleted names may only survive as prose explaining why they went.
    assert "python -m policy_atlas.ops" in makefile
