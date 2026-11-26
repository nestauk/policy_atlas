"""The announcement mailer and email layout."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from email import message_from_bytes, policy
from typing import Any

import boto3
import pytest
from botocore.awsrequest import AWSResponse
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from botocore.stub import ANY, Stubber

from policy_atlas.ops.errors import InvalidMessage
from policy_atlas.ops.mail import (
    Kind,
    MailSettings,
    Message,
    Rendered,
    SesMailer,
    proven_not_sent,
    render_announcement,
    ses_client,
)

SETTINGS = MailSettings(
    from_address="Policy Atlas <updates@example.org>",
    reply_to="team@example.net",
    site_url="https://site.example.org",
    api_url="https://api.example.org",
)
TOKEN = "0f8fad5b-d9cb-469f-a165-70867728950e"
UNSUB_PAGE = f"https://site.example.org/unsubscribe?token={TOKEN}"
UNSUB_HEADER = f"<https://api.example.org/api/v1/unsubscribe?token={TOKEN}>"
IMAGE = "https://site.example.org/email-images/abc.png"


def _render(message: Message, kind: Kind = "product_update") -> Rendered:
    token = TOKEN if kind == "product_update" else None
    return render_announcement(message, kind=kind, unsubscribe_token=token, settings=SETTINGS)


@pytest.fixture
def ses() -> Iterator[tuple[SesMailer, Stubber]]:
    client = boto3.client(
        "sesv2",
        region_name="eu-west-2",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    stubber = Stubber(client)
    stubber.activate()
    try:
        yield SesMailer(client, SETTINGS), stubber
    finally:
        stubber.deactivate()


def test_operator_text_is_escaped() -> None:
    rendered = _render(Message(subject='Tom & "Jerry"', body="<script>alert(1)</script>"))
    assert "<script>" not in rendered.html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered.html
    assert "Tom &amp; &quot;Jerry&quot;" in rendered.html


def test_body_becomes_paragraphs_and_a_list() -> None:
    body = "First line\nsecond line\n\nIntro\n- one\n- two"
    rendered = _render(Message(subject="News", body=body))
    assert "First line<br>second line</td>" in rendered.html
    assert ">Intro</td>" in rendered.html
    assert '<ul style="margin:0;padding-left:20px;"><li>one</li><li>two</li></ul>' in rendered.html


def test_a_placeholder_name_typed_by_the_operator_is_not_filled() -> None:
    rendered = _render(Message(subject="__BODY__", body="__FOOTER__ and __REPLY_TO__"))
    assert "__FOOTER__ and __REPLY_TO__" in rendered.html
    assert rendered.html.count("__BODY__") == 2  # the title and the heading


@pytest.mark.parametrize(
    "fields",
    [
        {"button_label": "Open", "button_url": "http://site.example.org"},
        {"button_label": "Open"},
        {"button_url": "https://site.example.org"},
    ],
)
def test_button_rules_are_refused(fields: dict[str, Any]) -> None:
    with pytest.raises(InvalidMessage):
        _render(Message(subject="News", body="Hi", **fields))


@pytest.mark.parametrize(
    "fields",
    [
        {"image_url": "https://elsewhere.example.com/email-images/a.png", "image_alt": "A"},
        {"image_url": IMAGE},
    ],
)
def test_picture_rules_are_refused(fields: dict[str, Any]) -> None:
    with pytest.raises(InvalidMessage):
        _render(Message(subject="News", body="Hi", **fields))


def test_a_product_update_has_the_unsubscribe_link_headers_and_footer() -> None:
    rendered = _render(Message(subject="News", body="Hi"))
    assert rendered.headers == {
        "List-Unsubscribe": UNSUB_HEADER,
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    assert (
        "You get this email because you have a Policy Atlas account. "
        f'<a href="{UNSUB_PAGE}" style="color:#5a5f6e;">Unsubscribe from product updates</a>. '
        "We still send service notices about your account."
    ) in rendered.html


def test_a_service_notice_has_no_unsubscribe_link_or_headers() -> None:
    rendered = _render(Message(subject="Downtime", body="Hi"), kind="service_notice")
    assert rendered.headers == {}
    assert "unsubscribe" not in rendered.html.lower()
    assert "unsubscribe" not in rendered.text.lower()
    assert (
        "You get this email because you have a Policy Atlas account. "
        "This is a service notice about your account."
    ) in rendered.html


def test_the_plain_text_part_carries_the_same_content() -> None:
    message = Message(
        subject="News",
        body="Hello\n\n- one\n- two",
        button_label="Open",
        button_url="https://site.example.org/x",
        image_url=IMAGE,
        image_alt="A map",
    )
    text = _render(message).text
    for piece in ["News", "Hello", "- one\n- two", "[A map]", "Open: https://site.example.org/x",
                  UNSUB_PAGE, "We still send service notices about your account."]:
        assert piece in text


def test_the_footer_names_the_reply_address() -> None:
    rendered = _render(Message(subject="News", body="Hi"))
    assert 'href="mailto:team@example.net"' in rendered.html
    assert "Questions? Reply to this email or write to team@example.net." in rendered.text


def test_ses_send_is_raw_to_one_recipient_with_from_reply_to_and_unsubscribe(
    ses: tuple[SesMailer, Stubber],
) -> None:
    mailer, stubber = ses
    captured: list[bytes] = []
    stubber.client.meta.events.register(
        "provide-client-params.sesv2.SendEmail",
        lambda params, **_: captured.append(params["Content"]["Raw"]["Data"]),
    )
    stubber.add_response(
        "send_email",
        {"MessageId": "m-1"},
        {
            "FromEmailAddress": SETTINGS.from_address,
            "Destination": {"ToAddresses": ["ana@example.com"]},
            "Content": {"Raw": {"Data": ANY}},
        },
    )
    rendered = _render(Message(subject="News", body="Hi"))
    mailer.send(to="ana@example.com", subject=rendered.subject, html=rendered.html,
                text=rendered.text, headers=rendered.headers)
    stubber.assert_no_pending_responses()

    assert UNSUB_HEADER.encode() in captured[0]
    sent = message_from_bytes(captured[0], policy=policy.default)
    assert sent["To"] == "ana@example.com"
    assert sent["From"] == SETTINGS.from_address
    assert sent["Reply-To"] == SETTINGS.reply_to
    assert sent["List-Unsubscribe"] == UNSUB_HEADER
    assert sent["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert {part.get_content_type() for part in sent.iter_parts()} == {"text/plain", "text/html"}


@pytest.mark.parametrize(
    ("subject", "headers"),
    [("News\nBcc: x@example.com", {}), ("News", {"List-Unsubscribe": "<a>\nBcc: x@example.com"})],
)
def test_a_line_break_in_a_header_is_refused_and_nothing_is_sent(
    ses: tuple[SesMailer, Stubber], subject: str, headers: dict[str, str]
) -> None:
    mailer, stubber = ses
    with pytest.raises(ValueError, match="linefeed"):
        mailer.send(to="ana@example.com", subject=subject, html="<p>x</p>", text="x",
                    headers=headers)
    stubber.assert_no_pending_responses()  # no send_email was queued, so none may run


def test_ses_suppressed_reads_every_page_and_maps_reasons(
    ses: tuple[SesMailer, Stubber],
) -> None:
    mailer, stubber = ses
    since = datetime(2026, 1, 1, tzinfo=UTC)
    at = datetime(2026, 2, 1, tzinfo=UTC)
    stubber.add_response(
        "list_suppressed_destinations",
        {
            "SuppressedDestinationSummaries": [
                {"EmailAddress": "Ana@Example.com", "Reason": "BOUNCE", "LastUpdateTime": at}
            ],
            "NextToken": "page-2",
        },
        {"StartDate": since},
    )
    stubber.add_response(
        "list_suppressed_destinations",
        {
            "SuppressedDestinationSummaries": [
                {"EmailAddress": "bo@example.com", "Reason": "COMPLAINT", "LastUpdateTime": at}
            ]
        },
        {"StartDate": since, "NextToken": "page-2"},
    )
    result = mailer.suppressed(since)
    stubber.assert_no_pending_responses()
    assert {address: entry.reason for address, entry in result.items()} == {
        "ana@example.com": "bounce",
        "bo@example.com": "complaint",
    }


def _ses_error(status: int, code: str) -> ClientError:
    response: Any = {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}
    return ClientError(response, "SendEmail")


@pytest.mark.parametrize(
    ("error", "not_sent"),
    [
        (InvalidMessage("the subject is empty", field="subject"), True),
        (ValueError("Header values may not contain linefeed"), True),
        (EndpointConnectionError(endpoint_url="https://email.example"), True),
        (ConnectTimeoutError(endpoint_url="https://email.example"), True),
        (_ses_error(400, "MessageRejected"), True),
        (_ses_error(429, "TooManyRequestsException"), True),
        (_ses_error(500, "InternalFailure"), False),
        (_ses_error(503, "ServiceUnavailable"), False),
        (ClientError({"Error": {"Code": "MessageRejected"}}, "SendEmail"), False),
        (ReadTimeoutError(endpoint_url="https://email.example"), False),
        (ConnectionClosedError(endpoint_url="https://email.example"), False),
        (OSError("connection reset"), False),
        (RuntimeError("anything else"), False),
    ],
)
def test_only_an_error_that_proves_the_email_did_not_go_counts_as_not_sent(
    error: Exception, not_sent: bool
) -> None:
    assert proven_not_sent(error) is not_sent


class _Body:
    def stream(self, **_: Any) -> Iterator[bytes]:
        yield b'{"message": "internal failure"}'


def test_the_ses_client_tries_a_send_once_and_has_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    client = ses_client("eu-west-2")
    attempts: list[str] = []

    def answer_500(request: Any, **_: Any) -> Any:
        attempts.append(request.url)
        no_headers: Any = {}
        return AWSResponse(request.url, 500, no_headers, _Body())

    client.meta.events.register("before-send.sesv2.SendEmail", answer_500)
    with pytest.raises(ClientError):
        SesMailer(client, SETTINGS).send(
            to="ana@example.com", subject="News", html="<p>x</p>", text="x", headers={}
        )

    assert len(attempts) == 1
    config: Any = client.meta.config
    assert config.connect_timeout <= 10
    assert config.read_timeout <= 30
