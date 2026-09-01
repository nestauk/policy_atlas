"""Structured-logging wiring at the deployed API entrypoint (task 033, Phase 0b).

`create_app` is what uvicorn calls directly in the container (`--factory`), so
it is the one place `configure_logging()` must run before anything else can
log — `runtime/orchestrate.py`'s `main()` only covers the local CLI path.
"""

from __future__ import annotations

import json
import logging

import pytest
import structlog

from policy_atlas.api.app import create_app
from policy_atlas.api.settings import Settings


def test_create_app_configures_json_logging_and_httpx_guard(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`create_app` must call `configure_logging()` first, so a JSON-format
    environment renders real structlog output and the httpx logger guard
    (rubric 15a) is applied on the deployed path, not only the CLI.
    """
    monkeypatch.setenv("LOG_FORMAT", "json")
    settings = Settings(
        "http://dev-issuer.local",
        "logging-entrypoint-test",
        "https://dev-issuer.local/jwks",
        None,
        "http://app.example.test",
        "postgresql+psycopg://unused/unused",
    )
    try:
        create_app(settings=settings)

        assert logging.getLogger("httpx").level == logging.WARNING

        log = structlog.get_logger()
        log.info("probe", key="value")

        out = capsys.readouterr().out.strip().splitlines()
        assert len(out) == 1
        record = json.loads(out[0])
        assert record["event"] == "probe"
        assert record["key"] == "value"
        assert "level" in record
        assert "timestamp" in record
    finally:
        structlog.reset_defaults()
