"""Static, Docker-free regression checks for the backend image boundary."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
DOCKERIGNORE_PATH = BACKEND_ROOT / ".dockerignore"
DOCKERFILE_PATH = BACKEND_ROOT / "Dockerfile"


def _ignore_patterns(path: Path) -> list[str]:
    """Return exclusion patterns from a gitignore-style file."""
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#") and not line.lstrip().startswith("!")
    ]


def _could_match_backend_context(pattern: str, source: Path) -> str | None:
    """Map a gitignore exclusion to the backend context when it can apply."""
    normalized = pattern.lstrip("/")
    if source == REPO_ROOT / ".gitignore" and "/" in normalized.rstrip("/"):
        backend_prefix = "backend/"
        if not normalized.startswith(backend_prefix):
            return None
        return normalized.removeprefix(backend_prefix)
    return normalized


def _dockerignore_covers(pattern: str, docker_patterns: set[str]) -> bool:
    """Return whether a Docker ignore rule exactly covers a Git ignore exclusion."""
    target = pattern.rstrip("/")
    for docker_pattern in docker_patterns:
        candidate = docker_pattern.rstrip("/")
        if candidate == target:
            return True
        if not any(token in candidate for token in "*?[") and target.startswith(f"{candidate}/"):
            return True
    return False


def test_dockerignore_covers_gitignored_backend_content() -> None:
    """Every relevant Git exclusion must also be excluded from Docker context."""
    docker_patterns = set(_ignore_patterns(DOCKERIGNORE_PATH))
    uncovered: list[str] = []
    for ignore_file in (REPO_ROOT / ".gitignore", BACKEND_ROOT / ".gitignore"):
        for pattern in _ignore_patterns(ignore_file):
            context_pattern = _could_match_backend_context(pattern, ignore_file)
            if context_pattern and not _dockerignore_covers(context_pattern, docker_patterns):
                uncovered.append(f"{ignore_file.relative_to(REPO_ROOT)}: {pattern}")

    assert not uncovered, "Uncovered gitignore patterns in backend Docker context:\n- " + "\n- ".join(
        uncovered
    )


def test_dockerfile_has_dockerignore_when_copying_context() -> None:
    """A broad context copy is allowed only when its Docker exclusions exist."""
    dockerfile = DOCKERFILE_PATH.read_text()
    if re.search(r"(?mi)^\s*copy(?:\s+--[^\s]+)*\s+\.\s+\.\s*$", dockerfile):
        assert DOCKERIGNORE_PATH.is_file(), "COPY . . requires backend/.dockerignore"


def test_dockerfile_runs_as_non_root_and_uses_factory_entrypoint() -> None:
    """The image must drop root and invoke the FastAPI factory entrypoint."""
    dockerfile = DOCKERFILE_PATH.read_text()
    users = [line.split(maxsplit=1)[1].strip() for line in dockerfile.splitlines() if line.startswith("USER ")]

    assert users, "Dockerfile must declare a USER"
    assert users[-1].lower() not in {"root", "0", "0:0"}
    assert (
        'CMD ["uvicorn", "policy_atlas.api.app:create_app", "--factory", "--host", '
        '"0.0.0.0", "--port", "8000"]'
    ) in dockerfile
