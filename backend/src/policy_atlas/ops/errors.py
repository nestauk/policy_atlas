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


class ResendTooSoon(OpsError):
    """Refusal raised while an invitation's one-hour cooldown is active."""

    def __init__(self, *, retry_after: datetime) -> None:
        self.retry_after = retry_after
        super().__init__(f"an invitation was sent recently; retry after {retry_after.isoformat()}")
