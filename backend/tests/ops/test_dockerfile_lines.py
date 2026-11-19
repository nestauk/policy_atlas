"""Two lines of ``backend/Dockerfile`` that no behavioural test exercises (task 057).

task 057 review: contract verifier 12. Both lines only matter inside a built
image running on AWS, so the suite pins them as text:

- ``python -m compileall``: compiles every Python file to bytecode at build time.
  Without it each fresh container (an API task or an ingest function) compiles
  about 6,500 files on its first import, adding seconds to every cold start (N13).
- ``chmod 755 /app``: ``useradd --create-home`` makes the home directory private
  (mode 700). AWS Lambda runs a container image as its own user, not the image's
  ``USER``, so with a 700 ``/app`` the ingest function cannot enter its own code
  directory and never starts.
"""

from __future__ import annotations

import re
from pathlib import Path

_DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def _lines() -> list[str]:
    return _DOCKERFILE.read_text(encoding="utf-8").splitlines()


def test_dockerfile_compiles_bytecode_at_build_time() -> None:
    assert any(
        line.lstrip().startswith("RUN") and "compileall" in line for line in _lines()
    )


def test_dockerfile_makes_app_readable_by_any_user() -> None:
    assert any(
        re.search(r"\bchmod\s+(?:-\S+\s+)*0?755\s+/app\s*$", line) for line in _lines()
    )


def test_dockerfile_cmd_has_keepalive_proxy_and_server_header_flags() -> None:
    # Keep-alive 125 s outlasts the load balancer's 120 s idle time (else 502s).
    cmd = next(line for line in _lines() if line.startswith("CMD"))
    assert '"--timeout-keep-alive", "125"' in cmd
    assert '"--proxy-headers"' in cmd
    assert '"--no-server-header"' in cmd


def test_dockerfile_copies_the_optional_ops_bundle_into_the_runtime_image() -> None:
    dockerfile = _DOCKERFILE.read_text(encoding="utf-8")
    assert "RUN mkdir -p /app/ops-ui" in dockerfile
    assert "COPY --from=builder --chown=app:app /app/ops-ui ./ops-ui" in dockerfile
