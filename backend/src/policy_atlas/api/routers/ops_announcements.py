"""Ops routes for announcement email: preview, test, picture, send, list, detail, retry.

Mounted beside :mod:`policy_atlas.api.routers.ops` on the operations service
only, behind the same ops-role check, and in the ops OpenAPI document. The
logic lives in :mod:`policy_atlas.ops.announcements`; these routes map its
refusals to answers and start the background sender after the commit.

Log lines and audit rows carry ids and counts only: never an email address,
a token, the subject or the message text.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from collections import Counter
from collections.abc import Mapping
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.app import ApiConflict, ApiUnprocessable
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract.ops import (
    AnnouncementCounts,
    AnnouncementCreatedOut,
    AnnouncementDetailOut,
    AnnouncementImageIn,
    AnnouncementImageOut,
    AnnouncementMessageIn,
    AnnouncementRecipientsIn,
    AnnouncementRecipientsOut,
    AnnouncementResultOut,
    AnnouncementSendIn,
    AnnouncementsOut,
    AnnouncementSummaryOut,
    AnnouncementTestIn,
    AudienceIn,
)
from policy_atlas.api.deps import (
    get_announcement_image_store,
    get_conn,
    get_engine,
    get_mail_settings,
    get_mailer,
    get_settings,
)
from policy_atlas.api.routers.ops import _queue_log as queue_log
from policy_atlas.api.routers.ops import after_commit, require_ops
from policy_atlas.api.settings import Settings
from policy_atlas.core import uploads
from policy_atlas.core.schema import (
    announcement,
    announcement_recipient,
    app_user,
    ops_action,
    organisation,
)
from policy_atlas.core.uploads import UploadStore
from policy_atlas.ops import announcements, commands
from policy_atlas.ops.announcements import _failure_code as failure_code
from policy_atlas.ops.errors import InvalidMessage, NotFound, OpsError
from policy_atlas.ops.mail import Mailer, MailSettings, Message, Suppressed, render_announcement

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/ops",
    tags=["ops"],
    dependencies=[Depends(after_commit), Depends(require_ops)],
)

#: A token no account holds: the public unsubscribe route answers 404 to it.
SAMPLE_TOKEN = "00000000-0000-0000-0000-000000000000"
IMAGE_MAX_BYTES = 1024 * 1024
_IMAGE_SUFFIX = {"image/png": "png", "image/jpeg": "jpg"}
_IMAGE_CACHE = "public, max-age=31536000, immutable"
_OVERLAY: dict[str, Literal["bounced", "marked_as_spam"]] = {
    "bounce": "bounced", "complaint": "marked_as_spam",
}

Actor = Annotated[AuthenticatedUser, Depends(require_ops)]
Conn = Annotated[Connection, Depends(get_conn)]


def _audience(body: AudienceIn) -> announcements.Audience:
    return announcements.Audience(
        everyone=body.everyone,
        cohort_ids=tuple(body.cohort_ids),
        org_ids=tuple(body.org_ids),
        user_ids=tuple(body.user_ids),
    )


def _message(body: AnnouncementMessageIn) -> Message:
    return Message(
        subject=body.subject,
        body=body.body,
        button_label=body.button_label,
        button_url=body.button_url,
        image_url=body.image_url,
        image_alt=body.image_alt,
    )


def _suppressed(mailer: Mailer) -> dict[str, Suppressed]:
    """Read the suppression list once; without it a send is not safe, so refuse (503)."""
    try:
        return mailer.suppressed()
    except Exception as error:
        log.warning("announcement.suppression_unreadable", reason=failure_code(error))
        raise HTTPException(503, "the email service's suppression list cannot be read") from None


def _recipients_out(built: announcements.RecipientList) -> AnnouncementRecipientsOut:
    return AnnouncementRecipientsOut.model_validate(
        {
            "chosen": built.chosen,
            "will_get": built.will_get,
            "left_out": built.left_out,
            "recipients": [vars(person) for person in built.recipients],
            "fingerprint": built.fingerprint,
        }
    )


def _action_id(conn: Connection, action: str, target: str) -> uuid.UUID:
    """The id of the audit row the announcement functions just wrote in this transaction."""
    action_id: uuid.UUID = conn.execute(
        select(ops_action.c.action_id)
        .where(ops_action.c.action == action, ops_action.c.target == target)
        .order_by(ops_action.c.at.desc())
        .limit(1)
    ).scalar_one()
    return action_id


def _counts(conn: Connection, ids: list[uuid.UUID]) -> dict[uuid.UUID, AnnouncementCounts]:
    by_id: dict[uuid.UUID, Counter[str]] = {i: Counter() for i in ids}
    if ids:
        for announcement_id, row_status, count in conn.execute(
            select(
                announcement_recipient.c.announcement_id,
                announcement_recipient.c.status,
                func.count(),
            )
            .where(announcement_recipient.c.announcement_id.in_(ids))
            .group_by(announcement_recipient.c.announcement_id, announcement_recipient.c.status)
        ):
            by_id[announcement_id][row_status] = count
    return {i: AnnouncementCounts(**counter) for i, counter in by_id.items()}


def _summaries(conn: Connection, announcement_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    query = (
        select(announcement, app_user.c.display_name.label("sent_by_name"))
        .outerjoin(app_user, app_user.c.user_id == announcement.c.sent_by)
        .order_by(announcement.c.created_at.desc(), announcement.c.announcement_id)
    )
    if announcement_id is not None:
        query = query.where(announcement.c.announcement_id == announcement_id)
    rows = [dict(row) for row in conn.execute(query).mappings()]
    counts = _counts(conn, [row["announcement_id"] for row in rows])
    for row in rows:
        row["counts"] = counts[row["announcement_id"]]
    return rows


def _start_sender(
    request: Request, engine: Engine, mailer: Mailer, mail_settings: MailSettings,
    announcement_id: uuid.UUID,
) -> None:
    """Queue the sender to start once the request's transaction has committed."""
    request.state.ops_after_commit.append(
        lambda: announcements.start_sender(engine, mailer, mail_settings, announcement_id)
    )


@router.post("/announcements/recipients", response_model=AnnouncementRecipientsOut)
def preview_recipients(
    body: AnnouncementRecipientsIn, conn: Conn,
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> AnnouncementRecipientsOut:
    """Who the announcement would go to, and who is left out and why. Writes nothing."""
    try:
        built = announcements.build_recipients(
            conn, kind=body.kind, audience=_audience(body.audience),
            suppressed=_suppressed(mailer),
        )
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    return _recipients_out(built)


@router.post("/announcements/test", status_code=status.HTTP_204_NO_CONTENT)
def send_test(
    body: AnnouncementTestIn, request: Request, actor: Actor, conn: Conn,
    mailer: Annotated[Mailer, Depends(get_mailer)],
    mail_settings: Annotated[MailSettings, Depends(get_mail_settings)],
) -> Response:
    """Send one test email to the operator's own address, subject prefixed ``[Test] ``."""
    own = conn.execute(
        select(app_user.c.email).where(app_user.c.user_id == actor.user_id)
    ).scalar_one_or_none()
    if not own:
        raise ApiConflict("ops_refused", "your account has no email address to send a test to")
    try:
        rendered = render_announcement(
            _message(body), kind=body.kind,
            unsubscribe_token=SAMPLE_TOKEN if body.kind == "product_update" else None,
            settings=mail_settings,
        )
    except InvalidMessage as exc:
        raise HTTPException(422, str(exc)) from None
    try:
        mailer.send(
            to=own, subject=f"[Test] {rendered.subject}", html=rendered.html, text=rendered.text,
            headers=rendered.headers,
        )
    except Exception as error:
        code = failure_code(error)
        log.warning("announcement.test_failed", actor=actor.user_id, reason=code)
        raise HTTPException(502, f"the test email was not sent ({code})") from None
    action_id = commands.record_action(
        conn, actor=actor.user_id, action="announcement.test", target=actor.user_id, outcome="ok"
    )
    queue_log(request, actor=actor.user_id, action="announcement.test", target=actor.user_id,
              outcome="ok", action_id=action_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/announcement-images", response_model=AnnouncementImageOut,
    status_code=status.HTTP_201_CREATED,
)
def add_image(
    body: AnnouncementImageIn, request: Request, actor: Actor, conn: Conn,
    store: Annotated[UploadStore, Depends(get_announcement_image_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnnouncementImageOut:
    """Store a PNG or JPEG of at most 1 MB under a random name; return its public address."""
    if settings.public_site_url is None:
        raise HTTPException(503, "the public site address is not configured")
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except binascii.Error:
        raise ApiUnprocessable("upload_type", "The file could not be read.") from None
    if len(data) > IMAGE_MAX_BYTES:
        raise ApiUnprocessable("upload_size", "The picture must be under 1 MB.")
    try:
        uploads.check(data, body.content_type)
    except uploads.UploadRefused as exc:
        raise ApiUnprocessable(exc.code, str(exc)) from None
    name = f"{uuid.uuid4()}.{_IMAGE_SUFFIX[body.content_type]}"
    store.put(f"email-images/{name}", data, body.content_type, cache_control=_IMAGE_CACHE)
    action_id = commands.record_action(
        conn, actor=actor.user_id, action="announcement.image", target=name, outcome="ok"
    )
    queue_log(request, actor=actor.user_id, action="announcement.image", target=name,
              outcome="ok", action_id=action_id)
    return AnnouncementImageOut(url=f"{settings.public_site_url}/email-images/{name}")


@router.post(
    "/announcements", response_model=AnnouncementCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
def send_announcement(
    body: AnnouncementSendIn, request: Request, actor: Actor, conn: Conn,
    engine: Annotated[Engine, Depends(get_engine)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    mail_settings: Annotated[MailSettings, Depends(get_mail_settings)],
) -> AnnouncementCreatedOut:
    """Record the announcement and its recipients; the sender starts after the commit."""
    try:
        announcement_id = announcements.create_announcement(
            conn, actor=actor.user_id, message=_message(body), kind=body.kind,
            audience=_audience(body.audience), fingerprint=body.fingerprint,
            suppressed=_suppressed(mailer), settings=mail_settings,
        )
    except InvalidMessage as exc:
        raise HTTPException(422, str(exc)) from None
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except announcements.RecipientsChanged as exc:
        raise ApiConflict(
            "recipients_changed", str(exc),
            _recipients_out(exc.recipients).model_dump(mode="json"),
        ) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    target = str(announcement_id)
    counts = _counts(conn, [announcement_id])[announcement_id]
    chosen = sum(counts.model_dump().values())
    queue_log(request, actor=actor.user_id, action="announcement.send", target=target,
              outcome="ok", action_id=_action_id(conn, "announcement.send", target),
              chosen=chosen, will_get=counts.pending)
    _start_sender(request, engine, mailer, mail_settings, announcement_id)
    return AnnouncementCreatedOut(announcement_id=announcement_id)


@router.get("/announcements", response_model=AnnouncementsOut)
def list_announcements(conn: Conn) -> AnnouncementsOut:
    """Every announcement, newest first, with its recipient counts by status."""
    return AnnouncementsOut(
        items=[AnnouncementSummaryOut.model_validate(row) for row in _summaries(conn)]
    )


@router.get("/announcements/{announcement_id}", response_model=AnnouncementDetailOut)
def get_announcement(
    announcement_id: uuid.UUID, request: Request, conn: Conn
) -> AnnouncementDetailOut:
    """One announcement and each person's result.

    A ``sent`` row whose address joined the suppression list after the send
    shows ``bounced`` or ``marked_as_spam`` as its overlay; nothing is stored.
    Without a mailer, or when the list cannot be read, no row has an overlay
    and ``suppression_unreadable`` is true.
    """
    found = _summaries(conn, announcement_id)
    if not found:
        raise HTTPException(404, f"no announcement {announcement_id}")
    row = found[0]
    mailer: Mailer | None = getattr(request.app.state, "mailer", None)
    suppressed: Mapping[str, Suppressed] = {}
    unreadable = mailer is None
    if mailer is not None:
        try:
            suppressed = mailer.suppressed(since=row["created_at"])
        except Exception as error:
            log.warning("announcement.suppression_unreadable", reason=failure_code(error))
            unreadable = True
    recipients = []
    for person in conn.execute(
        select(
            announcement_recipient.c.user_id,
            app_user.c.display_name.label("name"),
            announcement_recipient.c.email,
            organisation.c.name.label("organisation"),
            announcement_recipient.c.status,
            announcement_recipient.c.reason,
        )
        .join(app_user, app_user.c.user_id == announcement_recipient.c.user_id)
        .outerjoin(organisation, organisation.c.org_id == app_user.c.org_id)
        .where(announcement_recipient.c.announcement_id == announcement_id)
        .order_by(app_user.c.display_name, announcement_recipient.c.user_id)
    ).mappings():
        entry = (
            suppressed.get(person["email"].lower())
            if person["status"] == "sent" and person["email"]
            else None
        )
        recipients.append(
            AnnouncementResultOut(
                **person, overlay=_OVERLAY[entry.reason] if entry is not None else None
            )
        )
    return AnnouncementDetailOut.model_validate(
        {**row, "recipients": recipients, "suppression_unreadable": unreadable}
    )


@router.post("/announcements/{announcement_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_announcement(
    announcement_id: uuid.UUID, request: Request, actor: Actor, conn: Conn,
    engine: Annotated[Engine, Depends(get_engine)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    mail_settings: Annotated[MailSettings, Depends(get_mail_settings)],
) -> Response:
    """Put the failed rows back to pending and start the sender after the commit."""
    try:
        moved = announcements.retry_failed(conn, actor=actor.user_id,
                                           announcement_id=announcement_id)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    target = str(announcement_id)
    queue_log(request, actor=actor.user_id, action="announcement.retry", target=target,
              outcome="ok", action_id=_action_id(conn, "announcement.retry", target),
              moved=moved)
    _start_sender(request, engine, mailer, mail_settings, announcement_id)
    return Response(status_code=status.HTTP_202_ACCEPTED)
