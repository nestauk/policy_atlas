"""Pin: the suite-wide network deny (task 019 item 7b, pytest-socket) actually blocks.

Config lives in ``pyproject.toml``'s ``[tool.pytest.ini_options] addopts``
(``--disable-socket --allow-hosts=... --allow-unix-socket``); this is the one
permanent check that the config is wired up and doing something, so a future
addopts edit that silently drops the deny fails loudly here instead of only
being missed by the absence of a hygiene assertion elsewhere.
"""

import socket

import pytest
from pytest_socket import SocketConnectBlockedError


def test_suite_wide_socket_deny_blocks_non_allowed_host() -> None:
    """A connect attempt to a host outside the allowlist is blocked by pytest-socket."""
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(("example.com", 80), timeout=1)
