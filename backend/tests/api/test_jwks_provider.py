"""JWKS refresh discipline: one fetch per window, old keys kept on failure."""

from __future__ import annotations

import inspect
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from structlog.testing import capture_logs

from policy_atlas.api import auth
from policy_atlas.api.auth import (
    JwksProvider,
    JwtAuthenticator,
    get_current_user,
    get_optional_user,
)
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings

_ISSUER = "http://dev-issuer-a.local"
_CLIENT_ID = "client-a"


@pytest.fixture
def key_dir(tmp_path: Path) -> Path:
    """Create a file-backed development issuer with one key, ``a-1``."""
    directory = tmp_path / "issuer"
    init(directory, kid="a-1")
    return directory


@pytest.fixture
def settings(key_dir: Path) -> Settings:
    """Point the provider at the local development JWKS file."""
    return Settings(
        _ISSUER,
        _CLIENT_ID,
        None,
        key_dir / "jwks.json",
        "http://app.example.test",
        os.environ["DATABASE_URL"],
    )


def _count_reads(provider: JwksProvider, *, delay: float = 0.0) -> Callable[[], int]:
    """Wrap the provider's key-set source so each read is counted."""
    original = provider._read_jwks
    reads = 0
    lock = threading.Lock()

    def counting() -> dict[str, Any]:
        nonlocal reads
        with lock:
            reads += 1
        time.sleep(delay)  # widen the race window so a missing lock shows
        return original()

    provider._read_jwks = counting  # type: ignore[method-assign]
    return lambda: reads


def _advance_clock(monkeypatch: pytest.MonkeyPatch, seconds: float) -> None:
    """Move ``time.monotonic`` forward without sleeping."""
    real = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real() + seconds)


def test_forty_threads_on_unknown_kids_cause_one_fetch(settings: Settings) -> None:
    """Forty concurrent misses with different kids share one key-set read."""
    with httpx.Client() as client:
        provider = JwksProvider(settings, client)
        reads = _count_reads(provider, delay=0.05)
        barrier = threading.Barrier(40)
        outcomes: list[BaseException | None] = [None] * 40

        def lookup(index: int) -> None:
            barrier.wait()
            try:
                provider.get_key(f"unknown-kid-{index}")
            except BaseException as exc:  # noqa: BLE001 - recorded for the assert
                outcomes[index] = exc

        threads = [threading.Thread(target=lookup, args=(i,)) for i in range(40)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert reads() == 1
    assert all(isinstance(outcome, KeyError) for outcome in outcomes)


def test_valid_token_still_verifies_after_failed_refresh(
    settings: Settings, key_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing key source keeps the old keys and logs the failure."""
    token = mint_token("user-a", _ISSUER, _CLIENT_ID, 60, key_dir, kid="a-1")
    with httpx.Client() as client:
        authenticator = JwtAuthenticator(settings, client)
        assert authenticator.authenticate(token).user_id == "user-a"

        def broken_source() -> dict[str, Any]:
            raise httpx.ConnectError("https://secret.example/jwks unreachable")

        authenticator.jwks._read_jwks = broken_source  # type: ignore[method-assign]
        authenticator.jwks._expires_at = 0.0
        _advance_clock(monkeypatch, auth._MIN_REFRESH_INTERVAL_SECONDS + 1)
        with capture_logs() as logs:
            assert authenticator.authenticate(token).user_id == "user-a"

    failures = [entry for entry in logs if entry["event"] == "auth.jwks_refresh_failed"]
    assert failures == [
        {"event": "auth.jwks_refresh_failed", "log_level": "error", "error_class": "ConnectError"}
    ]


def test_a_key_set_with_no_usable_key_keeps_the_old_keys(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``keys`` list that holds no RSA key is a failed refresh, not an empty cache."""
    with httpx.Client() as client:
        provider = JwksProvider(settings, client)
        good = provider.get_key("a-1")
        provider._read_jwks = lambda: {"keys": [{"kty": "oct", "kid": "x"}]}  # type: ignore[method-assign]
        provider._expires_at = 0.0
        _advance_clock(monkeypatch, auth._MIN_REFRESH_INTERVAL_SECONDS + 1)
        with capture_logs() as logs:
            assert provider.get_key("a-1") is good
    assert {
        "event": "auth.jwks_refresh_failed",
        "log_level": "error",
        "error_class": "NoUsableKeys",
    } in logs


def test_a_failed_first_fetch_does_not_hold_the_window(settings: Settings) -> None:
    """With no keys at all, the next lookup may try again at once (a blip at boot)."""
    with httpx.Client() as client:
        provider = JwksProvider(settings, client)
        working = provider._read_jwks

        def broken_source() -> dict[str, Any]:
            raise httpx.ConnectError("unreachable")

        provider._read_jwks = broken_source  # type: ignore[method-assign]
        with pytest.raises(httpx.ConnectError):
            provider.get_key("a-1")
        provider._read_jwks = working  # type: ignore[method-assign]
        assert provider.get_key("a-1") is not None  # no clock advance needed


def test_new_key_is_found_once_the_interval_has_passed(
    settings: Settings, key_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rotated-in key is refused inside the window and found after it."""
    with httpx.Client() as client:
        provider = JwksProvider(settings, client)
        reads = _count_reads(provider)
        provider.get_key("a-1")
        init(key_dir, kid="a-2")
        with pytest.raises(KeyError):
            provider.get_key("a-2")
        assert reads() == 1

        _advance_clock(monkeypatch, auth._MIN_REFRESH_INTERVAL_SECONDS + 1)
        with capture_logs() as logs:
            assert provider.get_key("a-2") is not None

    assert reads() == 2
    assert {"event": "auth.jwks_refreshed", "log_level": "info", "key_count": 2} in logs


def test_auth_dependencies_are_synchronous() -> None:
    """FastAPI must run both dependencies on its thread pool, not the event loop."""
    assert not inspect.iscoroutinefunction(get_current_user)
    assert not inspect.iscoroutinefunction(get_optional_user)
