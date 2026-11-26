"""Announcement email: the mailer seam and the email layout.

Two halves:

- **The mailer** sends one email to one person and reads the suppression list
  (the addresses Amazon SES, the Simple Email Service, will no longer send to
  because they bounced or their owner marked our email as spam).
  :class:`SesMailer` talks to SES; :class:`MemoryMailer` keeps emails in a list,
  for local work and tests.
- **The layout**: :func:`render_announcement` turns the operator's fields into a
  subject, an HTML body, a plain-text body and the extra headers.

Each email is built with the standard library's ``EmailMessage``. Its default
rules refuse a line break in any header value, so operator text can never add a
header of its own (header injection). Nothing here catches that error.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.message import EmailMessage
from importlib.resources import files
from typing import TYPE_CHECKING, Any, Literal, Protocol
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
)

from policy_atlas.ops.errors import InvalidMessage

if TYPE_CHECKING:
    from mypy_boto3_sesv2.client import SESV2Client

Kind = Literal["product_update", "service_notice"]

SUBJECT_MAX = 150
BODY_MAX = 10_000
BUTTON_LABEL_MAX = 40
IMAGE_ALT_MAX = 200

#: Serialise without folding long header lines. The default folding wraps a
#: long ``List-Unsubscribe`` address in encoded-word syntax, which mail
#: providers do not read as a link. Lines stay within the 998-character limit
#: of the email standard because every header value here is short.
_WIRE = policy.SMTP.clone(max_line_length=None)

_LAYOUT = files("policy_atlas.ops").joinpath("announcement.html").read_text(encoding="utf-8")
_PLACEHOLDER = re.compile(r"__(SUBJECT|LOGO_URL|BODY|IMAGE|BUTTON|FOOTER|REPLY_TO)__")

_CELL = '<tr><td style="padding:16px 32px 0 32px;font-size:16px;line-height:1.55;">{}</td></tr>'
_LIST = '<ul style="margin:0;padding-left:20px;">{}</ul>'
_IMAGE = (
    '<tr><td style="padding:20px 32px 0 32px;"><img src="{}" alt="{}" width="496" '
    'style="display:block;width:100%;max-width:496px;height:auto;border:0;"></td></tr>'
)
_BUTTON = (
    '<tr><td style="padding:20px 32px 0 32px;"><a href="{}" style="display:inline-block;'
    "background:#0000ff;color:#ffffff;text-decoration:none;font-size:16px;font-weight:600;"
    'padding:14px 24px;">{}</a></td></tr>'
)
_ACCOUNT_LINE = "You get this email because you have a Policy Atlas account."
_SERVICE_LINE = "This is a service notice about your account."
_UNSUBSCRIBE_WORDS = "Unsubscribe from product updates"
_STILL_SERVICE = "We still send service notices about your account."


@dataclass(frozen=True)
class MailSettings:
    """Where announcement email comes from and where its links point.

    Attributes:
        from_address: The sender, for example ``Policy Atlas <updates@example.org>``.
        reply_to: The address a reply goes to.
        site_url: The public site address, no trailing slash.
        api_url: The public API address, no trailing slash.
    """

    from_address: str
    reply_to: str
    site_url: str
    api_url: str


@dataclass(frozen=True)
class Suppressed:
    """Why and since when SES refuses to send to an address.

    Attributes:
        reason: ``bounce`` (the address bounced) or ``complaint`` (marked as spam).
        at: When SES last updated the entry.
    """

    reason: Literal["bounce", "complaint"]
    at: datetime


class Mailer(Protocol):
    """Sends one email to one person and reads the suppression list."""

    def send(
        self, *, to: str, subject: str, html: str, text: str, headers: Mapping[str, str]
    ) -> None:
        """Send one email to exactly one recipient.

        Args:
            to: The one recipient address.
            subject: The subject line.
            html: The HTML body.
            text: The plain-text body.
            headers: Extra headers only; the mailer adds ``From`` and ``Reply-To``.

        Raises:
            ValueError: A header value holds a line break; nothing is sent.
        """
        ...

    def suppressed(self, since: datetime | None = None) -> dict[str, Suppressed]:
        """Read the suppression list.

        Args:
            since: Only entries updated at or after this time; ``None`` for all.

        Returns:
            Each address, lower-cased, with its reason and time.
        """
        ...


@dataclass(frozen=True)
class SentEmail:
    """One email :class:`MemoryMailer` accepted, as fields and as the built message."""

    to: str
    subject: str
    html: str
    text: str
    headers: dict[str, str]
    message: EmailMessage


def build_message(
    settings: MailSettings,
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
    headers: Mapping[str, str],
) -> EmailMessage:
    """Build the email both mailers send: a plain-text part and an HTML alternative.

    Args:
        settings: Supplies ``From`` and ``Reply-To``.
        to: The one recipient.
        subject: The subject line.
        html: The HTML body.
        text: The plain-text body.
        headers: Extra headers (the unsubscribe headers).

    Returns:
        The message.

    Raises:
        ValueError: A header value holds a line break (the standard library's
            own refusal, kept as the guard against header injection).
    """
    message = EmailMessage()
    message["From"] = settings.from_address
    message["To"] = to
    message["Reply-To"] = settings.reply_to
    message["Subject"] = subject
    for name, value in headers.items():
        message[name] = value
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    return message


def ses_client(region: str | None) -> SESV2Client:
    """Build the SES client the ops server sends with.

    The client tries each call once: an automatic retry after a lost answer
    could send a second copy. A refusal for sending too fast (throttling) then
    reaches the caller as an error instead of being retried. The timeouts are
    short so a stuck call does not hold up the sender for long.

    Args:
        region: The AWS region; ``None`` takes the default.

    Returns:
        The client; credentials come from the environment (the task role).
    """
    return boto3.client(
        "sesv2",
        region_name=region,
        config=Config(
            retries={"total_max_attempts": 1, "mode": "standard"},
            connect_timeout=5,
            read_timeout=15,
        ),
    )


class SesMailer:
    """Sends through Amazon SES (version 2 of its API) as raw email.

    Raw, because SES's simple content type cannot carry the unsubscribe headers.
    """

    def __init__(self, client: SESV2Client, settings: MailSettings) -> None:
        self._client = client
        self._settings = settings

    def send(
        self, *, to: str, subject: str, html: str, text: str, headers: Mapping[str, str]
    ) -> None:
        """Send one email; an SES error reaches the caller as raised."""
        message = build_message(
            self._settings, to=to, subject=subject, html=html, text=text, headers=headers
        )
        self._client.send_email(
            FromEmailAddress=self._settings.from_address,
            Destination={"ToAddresses": [to]},
            Content={"Raw": {"Data": message.as_bytes(policy=_WIRE)}},
        )

    def suppressed(self, since: datetime | None = None) -> dict[str, Suppressed]:
        """Read every page of the account's suppression list."""
        # ponytail: the whole list is read on every call, fine for hundreds of
        # entries; at thousands, cache it or follow the SES event stream instead.
        result: dict[str, Suppressed] = {}
        request: dict[str, Any] = {} if since is None else {"StartDate": since}
        while True:
            page = self._client.list_suppressed_destinations(**request)
            for entry in page.get("SuppressedDestinationSummaries", []):
                reason: Literal["bounce", "complaint"] = (
                    "bounce" if entry["Reason"] == "BOUNCE" else "complaint"
                )
                result[entry["EmailAddress"].lower()] = Suppressed(
                    reason=reason, at=entry["LastUpdateTime"]
                )
            token = page.get("NextToken")
            if not token:
                return result
            request["NextToken"] = token


class MemoryMailer:
    """Keeps emails in memory, for local work and tests.

    Attributes:
        sent: Every email accepted, in order.
        suppression: The suppression list a test fills, keyed by lower-cased address.
        on_send: Called with the recipient before an email is kept; a test makes
            it raise whatever error it needs to stand for a failed send.
    """

    def __init__(self, settings: MailSettings) -> None:
        self._settings = settings
        self.sent: list[SentEmail] = []
        self.suppression: dict[str, Suppressed] = {}
        self.on_send: Callable[[str], None] | None = None

    def send(
        self, *, to: str, subject: str, html: str, text: str, headers: Mapping[str, str]
    ) -> None:
        """Build the email as :class:`SesMailer` would and keep it."""
        message = build_message(
            self._settings, to=to, subject=subject, html=html, text=text, headers=headers
        )
        if self.on_send is not None:
            self.on_send(to)
        self.sent.append(
            SentEmail(to=to, subject=subject, html=html, text=text,
                      headers=dict(headers), message=message)
        )

    def suppressed(self, since: datetime | None = None) -> dict[str, Suppressed]:
        """Return the filled-in list, cut to ``since`` when given."""
        return {
            address: entry
            for address, entry in self.suppression.items()
            if since is None or entry.at >= since
        }


def failure_code(error: Exception) -> str:
    """A short code for a failed mailer call: the SES error code, or the error's class name.

    Never the error's message, which can hold the address.

    Args:
        error: What the mailer raised.

    Returns:
        The code, safe to log.
    """
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code")
        if code:
            return str(code)
    return type(error).__name__


def proven_not_sent(error: Exception) -> bool:
    """Whether a failed mailer call proves the email did not go.

    True only when the message could not be built (:class:`InvalidMessage`, or
    the ``ValueError`` the header guard raises), when no connection to SES was
    made (``EndpointConnectionError``, ``ConnectTimeoutError``), or when SES
    answered with a refusal of the request (an HTTP status from 400 to 499,
    which includes throttling and ``MessageRejected``). Anything else, such as
    an SES server error (5xx), a read timeout or a closed connection, is
    unclear: SES may have accepted the email and the answer was lost.

    Args:
        error: What the mailer raised.

    Returns:
        ``True`` when sending again cannot give the person a second copy.
    """
    if isinstance(
        error, InvalidMessage | ValueError | EndpointConnectionError | ConnectTimeoutError
    ):
        return True
    if isinstance(error, ClientError):
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return isinstance(status, int) and 400 <= status < 500
    return False


@dataclass(frozen=True)
class Message:
    """What the operator writes. The last four fields are optional.

    Attributes:
        subject: The subject line, also the heading in the email.
        body: Paragraphs split by an empty line; lines starting with "- " make a list.
        button_label: The button's words; goes with ``button_url``.
        button_url: The button's ``https://`` link.
        image_url: A picture address the picture upload returned.
        image_alt: The picture's description; goes with ``image_url``.
    """

    subject: str
    body: str
    button_label: str | None = None
    button_url: str | None = None
    image_url: str | None = None
    image_alt: str | None = None


@dataclass(frozen=True)
class Rendered:
    """One email ready for :meth:`Mailer.send`."""

    subject: str
    html: str
    text: str
    headers: dict[str, str] = field(default_factory=dict)


def render_announcement(
    message: Message, *, kind: Kind, unsubscribe_token: str | None, settings: MailSettings
) -> Rendered:
    """Turn the operator's fields into one person's email.

    Args:
        message: The operator's fields.
        kind: ``product_update`` (with unsubscribe link and headers) or
            ``service_notice`` (with neither).
        unsubscribe_token: The person's token; required for a product update.
        settings: The site and API addresses and the reply address.

    Returns:
        The subject, the HTML and plain-text bodies, and the extra headers.

    Raises:
        InvalidMessage: A field breaks a rule (empty, too long, a link or
            picture address not allowed, half of a pair missing).
        ValueError: A product update without a token, or an unknown kind.
    """
    _check(message, settings)
    if kind not in ("product_update", "service_notice"):
        raise ValueError(f"unknown announcement kind {kind!r}")

    blocks = _blocks(message.body)
    html_body = "\n".join(
        _CELL.format(_LIST.format("".join(f"<li>{html.escape(item)}</li>" for item in lines)))
        if is_list
        else _CELL.format("<br>".join(html.escape(line) for line in lines))
        for is_list, lines in blocks
    )
    text_parts = [message.subject] + [
        "\n".join(f"- {item}" if is_list else item for item in lines) for is_list, lines in blocks
    ]

    image = button = ""
    if message.image_url and message.image_alt:
        image = _IMAGE.format(html.escape(message.image_url), html.escape(message.image_alt))
        text_parts.append(f"[{message.image_alt}]")
    if message.button_label and message.button_url:
        button = _BUTTON.format(html.escape(message.button_url), html.escape(message.button_label))
        text_parts.append(f"{message.button_label}: {message.button_url}")

    headers: dict[str, str] = {}
    if kind == "product_update":
        if unsubscribe_token is None:
            raise ValueError("a product update needs the person's unsubscribe token")
        token = quote(unsubscribe_token, safe="")
        page = f"{settings.site_url}/unsubscribe?token={token}"
        footer = (
            f'{_ACCOUNT_LINE} <a href="{html.escape(page)}" style="color:#5a5f6e;">'
            f"{_UNSUBSCRIBE_WORDS}</a>. {_STILL_SERVICE}"
        )
        text_parts.append(f"{_ACCOUNT_LINE}\n{_UNSUBSCRIBE_WORDS}: {page}\n{_STILL_SERVICE}")
        headers = {
            "List-Unsubscribe": f"<{settings.api_url}/api/v1/unsubscribe?token={token}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    else:
        footer = f"{_ACCOUNT_LINE} {_SERVICE_LINE}"
        text_parts.append(footer)
    text_parts.append(f"Questions? Reply to this email or write to {settings.reply_to}.")

    values = {
        "SUBJECT": html.escape(message.subject),
        "LOGO_URL": html.escape(f"{settings.site_url}/brand/email-logo.png"),
        "BODY": html_body,
        "IMAGE": image,
        "BUTTON": button,
        "FOOTER": footer,
        "REPLY_TO": html.escape(settings.reply_to),
    }
    # One pass: text the operator typed is never scanned for placeholders again.
    page_html = _PLACEHOLDER.sub(lambda match: values[match.group(1)], _LAYOUT)
    return Rendered(
        subject=message.subject, html=page_html, text="\n\n".join(text_parts) + "\n",
        headers=headers,
    )


def _blocks(body: str) -> list[tuple[bool, list[str]]]:
    """Split the body into (is a list, lines) runs; list lines lose their "- "."""
    runs: list[tuple[bool, list[str]]] = []
    for block in re.split(r"\n\s*\n", body.replace("\r\n", "\n").strip()):
        previous: bool | None = None
        for line in block.split("\n"):
            is_item = line.startswith("- ")
            content = line[2:] if is_item else line
            if is_item == previous:
                runs[-1][1].append(content)
            else:
                runs.append((is_item, [content]))
            previous = is_item
    return runs


def _check(message: Message, settings: MailSettings) -> None:
    """Apply the field rules; raise :class:`InvalidMessage` on the first broken one."""
    if not message.subject.strip():
        raise InvalidMessage("the subject is empty", field="subject")
    if "\n" in message.subject or "\r" in message.subject:
        raise InvalidMessage("the subject must be one line", field="subject")
    if len(message.subject) > SUBJECT_MAX:
        raise InvalidMessage(
            f"the subject is longer than {SUBJECT_MAX} characters", field="subject"
        )
    if not message.body.strip():
        raise InvalidMessage("the message is empty", field="body")
    if len(message.body) > BODY_MAX:
        raise InvalidMessage(f"the message is longer than {BODY_MAX} characters", field="body")
    if bool(message.button_label) != bool(message.button_url):
        raise InvalidMessage("a button needs both its words and its link", field="button_label")
    if message.button_url and not message.button_url.startswith("https://"):
        raise InvalidMessage("the button link must start with https://", field="button_url")
    if message.button_label and len(message.button_label) > BUTTON_LABEL_MAX:
        raise InvalidMessage(
            f"the button words are longer than {BUTTON_LABEL_MAX} characters", field="button_label"
        )
    if bool(message.image_url) != bool(message.image_alt):
        raise InvalidMessage(
            "a picture needs both its address and its description", field="image_alt"
        )
    if message.image_url and not message.image_url.startswith(
        f"{settings.site_url}/email-images/"
    ):
        raise InvalidMessage("use a picture added on this page", field="image_url")
    if message.image_alt and len(message.image_alt) > IMAGE_ALT_MAX:
        raise InvalidMessage(
            f"the picture description is longer than {IMAGE_ALT_MAX} characters", field="image_alt"
        )
