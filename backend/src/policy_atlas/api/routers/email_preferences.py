"""Public routes that switch a person's product-update emails off and on.

The link in each product-update email carries the person's unsubscribe token
in its query string. No sign-in: whoever holds the link holds the choice.
Mail providers post to the unsubscribe address themselves (the "one-click"
unsubscribe of RFC 8058, the email standard for it), with a fixed form body,
no cookie and no ``Origin`` header, so the routes ignore the body entirely.

The token is a secret in an address, so it must never reach an application
log line: :func:`~policy_atlas.core.logging.drop_token_from_access_log`
removes it from uvicorn's access log (the web server's one line per request).
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, update
from sqlalchemy.engine import Connection

from policy_atlas.api.deps import get_conn
from policy_atlas.core.logging import RESUBSCRIBE_PATH, UNSUBSCRIBE_PATH
from policy_atlas.core.schema import app_user

log = structlog.get_logger()

router = APIRouter(tags=["email_preferences"])


def _parse_token(token: str | None) -> uuid.UUID:
    """Read the token from the query string, or answer 404.

    A missing or badly formed token answers 404 like an unknown one, so the
    answer never says which of the three it was.
    """
    try:
        return uuid.UUID(token or "")
    except ValueError:
        raise HTTPException(status_code=404) from None


@router.post(
    UNSUBSCRIBE_PATH,
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={404: {"description": "Unknown, missing or badly formed token."}},
)
def unsubscribe(
    conn: Annotated[Connection, Depends(get_conn)], token: str | None = None
) -> Response:
    """Stop product-update emails for the person who holds this token.

    Safe to repeat: a second call keeps the first time. A deactivated
    account's token still works, because the person's choice stands.

    Args:
        conn: Open database connection.
        token: The person's unsubscribe token from the email link.

    Returns:
        An empty 204 answer.

    Raises:
        HTTPException: 404 when the token is missing, badly formed or unknown.
    """
    user_id = conn.execute(
        update(app_user)
        .where(app_user.c.unsubscribe_token == _parse_token(token))
        .values(
            updates_unsubscribed_at=func.coalesce(app_user.c.updates_unsubscribed_at, func.now())
        )
        .returning(app_user.c.user_id)
    ).scalar_one_or_none()
    return _answer(user_id, "unsubscribed")


@router.post(
    RESUBSCRIBE_PATH,
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={404: {"description": "Unknown, missing or badly formed token."}},
)
def resubscribe(
    conn: Annotated[Connection, Depends(get_conn)], token: str | None = None
) -> Response:
    """Start product-update emails again for the person who holds this token.

    Args:
        conn: Open database connection.
        token: The person's unsubscribe token from the email link.

    Returns:
        An empty 204 answer.

    Raises:
        HTTPException: 404 when the token is missing, badly formed or unknown.
    """
    user_id = conn.execute(
        update(app_user)
        .where(app_user.c.unsubscribe_token == _parse_token(token))
        .values(updates_unsubscribed_at=None)
        .returning(app_user.c.user_id)
    ).scalar_one_or_none()
    return _answer(user_id, "resubscribed")


def _answer(user_id: str | None, outcome: str) -> Response:
    """Log the outcome (never the token) and answer 204, or 404 for no account."""
    if user_id is None:
        log.info("email_preferences.changed", outcome="unknown_token")
        raise HTTPException(status_code=404)
    log.info("email_preferences.changed", outcome=outcome, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

