"""Refusal types the operator CLI raises."""

import uuid
from datetime import datetime


class OpsError(Exception):
    """A refusal the operator can act on.

    Every message is written for the person at the terminal and names the way
    forward where one exists ("use ``user enrol``", "run ``user resync``
    first"). :func:`policy_atlas.ops.cli.main` catches it, prints it to stderr
    and exits non-zero; nothing else in the package raises it for control flow.

    The distinction that matters: an :class:`OpsError` means *nothing was
    written*, except where the message says otherwise — ``user create``'s
    database-failure path is the single exception, and it says so in the text
    because the Cognito account it kept is real.
    """


class EnrolledElsewhere(OpsError):
    """Refusal raised when an account belongs to another organisation."""

    def __init__(self, *, sub: str, org_name: str, org_id: uuid.UUID, email: str) -> None:
        self.sub = sub
        self.org_name = org_name
        self.org_id = org_id
        super().__init__(
            f"{email} is already in {org_name}. Nothing was written. Move them from the "
            "People list (`user enrol`)."
        )


class Deactivated(OpsError):
    """Refusal raised when an account is deactivated and the path may not reactivate it.

    Only an operator's "Add person" or "Reactivate" turns a login back on; the
    waitlist approval and the self-signup sweep refuse (contract 066 B5).
    """

    def __init__(self, *, email: str) -> None:
        super().__init__(
            f"{email} is deactivated. Nothing was written. Reactivate them on People first."
        )


class ResendTooSoon(OpsError):
    """Refusal raised while an invitation's one-hour cooldown is active."""

    def __init__(self, *, retry_after: datetime) -> None:
        self.retry_after = retry_after
        super().__init__(f"an invitation was sent recently; retry after {retry_after.isoformat()}")


class NotFound(OpsError):
    """Refusal raised when the row a command was asked to act on does not exist.

    The ops routes answer it with 404; every other refusal is a 409. A typed
    class, so the routes never classify by message text.
    """


class InvalidMessage(OpsError):
    """Refusal raised when an announcement's fields break a rule.

    The ops routes answer it with 422 (a field rule), not the 409 of other
    refusals. A typed class, so the routes never classify by message text.

    Attributes:
        field: The request field that broke the rule, so a page can show the
            message under that field.
    """

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field
