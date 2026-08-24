"""How a person is named on screen, and what is never used to name them.

Contract 033 § 3b pins one rule harder than any other in the identity strand:
**``owner_display`` never falls back to the email.** An email fallback would
print every colleague's address on every row and card, and would let an admin
harvest ``{email, organisation}`` for every owner in the system — the user
directory the contract declares Out, reached by another door. So the ladder is
exactly two rungs, and the second one is derived from the token subject:

1. ``app_user.display_name`` — ``NOT NULL`` in the schema and required at
   enrolment, so an enrolled person always has one.
2. the **sub rendering** (:func:`sub_display`) — for a signed-in person who has
   no ``app_user`` row yet. That is a real state: ``get_current_user`` is
   DB-free, so a subject exists from the first authenticated request and the
   row appears only when ``GET /api/v1/me`` first runs.

There is no third rung. A row whose ``owner_user_id`` is ``NULL`` (the
``runtime/orchestrate.py`` CLI rows, which an admin can see per contract § 11)
has no person to name at all, and :func:`owner_display_for` returns ``None`` —
the API says "no owner" rather than inventing a placeholder. Choosing the
placeholder glyph is a rendering decision and belongs to the frontend.
"""

from __future__ import annotations

#: How many leading characters of the token subject the sub rendering keeps.
#: A Cognito ``sub`` is a UUID, so eight hex characters read as an identifier
#: while staying short enough for a table cell.
SUB_DISPLAY_CHARS = 8


def sub_display(user_id: str) -> str:
    """Render a token subject as a stable, non-identifying display name.

    Deterministic: the same subject always renders the same string, so the
    name ``GET /api/v1/me`` writes into a bare ``app_user`` row is the same
    name a listing derives for an owner who has no row yet, and the two
    surfaces never disagree.

    Args:
        user_id: The caller's token subject.

    Returns:
        A short human-readable rendering of the subject. Never an email —
        the subject is a generated UUID, not the address (contract § 3b: the
        pool is ``UsernameAttributes: ["email"]``, so ``cognito:username`` is
        a UUID and the address never reaches the API).
    """
    return f"User {user_id[:SUB_DISPLAY_CHARS]}"


def owner_display_for(owner_user_id: str | None, display_name: str | None) -> str | None:
    """Resolve the display name shown for a row's owner.

    Args:
        owner_user_id: The row's ``owner_user_id``, or ``None`` for the
            ownerless CLI rows.
        display_name: The owner's ``app_user.display_name`` when they have a
            row, else ``None``.

    Returns:
        The owner's display name, the sub rendering when they have no
        ``app_user`` row, or ``None`` when the row has no owner. Never the
        email under any branch.
    """
    if owner_user_id is None:
        return None
    return display_name if display_name is not None else sub_display(owner_user_id)
