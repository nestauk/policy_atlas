"""Coverage for the retention script `scripts/prune_unlinked_snapshots.py` (task 057, D3, N12).

The script opens its own transactions, so every test seeds *committed* rows through
the session `engine` fixture and removes them afterwards. Seeded snapshots are dated
~11 years back and the script runs with a 10-year cutoff, so rows other tests leave
behind (all dated now) are never candidates here.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError

from policy_atlas.core.schema import (
    chunk,
    chunk_embedding,
    source_snapshot,
    task_source_snapshot,
)
from tests.helpers import now, seed_task_and_run

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "prune_unlinked_snapshots.py"

_AGE_DAYS = 4000
_CUTOFF_DAYS = 3650


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prune_unlinked_snapshots", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["prune_unlinked_snapshots"] = module
    spec.loader.exec_module(module)
    return module


prune = _load()


class _Seeder:
    """Seeds committed snapshots and link rows; removes everything it made."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.snapshots: list[uuid.UUID] = []
        self.links: list[uuid.UUID] = []
        self.tasks: list[uuid.UUID] = []
        with engine.begin() as conn:
            self.task_id, _ = seed_task_and_run(conn)
        self.tasks.append(self.task_id)

    def snapshot(
        self, *, basis: str = "full_text", age_days: int = _AGE_DAYS, chunks: int = 2
    ) -> uuid.UUID:
        snapshot_id = uuid.uuid4()
        created = now() - timedelta(days=age_days)
        with self.engine.begin() as conn:
            conn.execute(
                source_snapshot.insert().values(
                    source_snapshot_id=snapshot_id,
                    content_hash=str(uuid.uuid4()),
                    text_basis=basis,
                    source_locator=f"prune-{snapshot_id}",
                    metadata={},
                    created_at=created,
                )
            )
            for index in range(chunks):
                chunk_id = uuid.uuid4()
                conn.execute(
                    chunk.insert().values(
                        chunk_id=chunk_id,
                        source_snapshot_id=snapshot_id,
                        sequence=index,
                        content=f"passage {index}",
                        content_hash=str(uuid.uuid4()),
                        locator={},
                        segmentation_policy="manual_v1",
                        created_at=created,
                    )
                )
                conn.execute(
                    chunk_embedding.insert().values(
                        chunk_embedding_id=uuid.uuid4(),
                        chunk_id=chunk_id,
                        embedding_profile="test_profile",
                        unit_policy="test_units",
                        unit_index=0,
                        unit_locator={"start": 0, "end": 9},
                        embedding=[0.0] * 1536,
                        tokens=["passage"],
                        created_at=created,
                    )
                )
        self.snapshots.append(snapshot_id)
        return snapshot_id

    def link_values(
        self, *, envelope: uuid.UUID, full_text: uuid.UUID | None
    ) -> dict[str, object]:
        link_id = uuid.uuid4()
        self.links.append(link_id)
        return {
            "task_source_snapshot_id": link_id,
            "task_id": self.task_id,
            "source_snapshot_id": envelope,
            "origin": "acquired",
            "run_id": None,
            "ingested_at": now(),
            "full_text_snapshot_id": full_text,
            "full_text_status": "ingested" if full_text else "not_attempted",
        }

    def link(self, *, envelope: uuid.UUID, full_text: uuid.UUID | None = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                task_source_snapshot.insert().values(
                    **self.link_values(envelope=envelope, full_text=full_text)
                )
            )

    def cleanup(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM task_source_snapshot WHERE task_source_snapshot_id = ANY(:i)"),
                {"i": self.links},
            )
            conn.execute(
                text(
                    "DELETE FROM chunk_embedding WHERE chunk_id IN (SELECT chunk_id FROM chunk "
                    "WHERE source_snapshot_id = ANY(:i))"
                ),
                {"i": self.snapshots},
            )
            conn.execute(
                text("DELETE FROM chunk WHERE source_snapshot_id = ANY(:i)"),
                {"i": self.snapshots},
            )
            conn.execute(
                text("DELETE FROM source_snapshot WHERE source_snapshot_id = ANY(:i)"),
                {"i": self.snapshots},
            )
            conn.execute(text("DELETE FROM runs WHERE task_id = ANY(:i)"), {"i": self.tasks})
            conn.execute(text("DELETE FROM task WHERE task_id = ANY(:i)"), {"i": self.tasks})


@pytest.fixture
def seeder(engine: Engine) -> Generator[_Seeder, None, None]:
    s = _Seeder(engine)
    try:
        yield s
    finally:
        s.cleanup()


def _counts(engine: Engine, snapshot_id: uuid.UUID) -> tuple[int, int, int]:
    """Return (snapshot rows, chunk rows, embedding rows) for one snapshot id."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT (SELECT count(*) FROM source_snapshot WHERE source_snapshot_id = :s), "
                "(SELECT count(*) FROM chunk WHERE source_snapshot_id = :s), "
                "(SELECT count(*) FROM chunk_embedding WHERE chunk_id IN "
                " (SELECT chunk_id FROM chunk WHERE source_snapshot_id = :s))"
            ),
            {"s": snapshot_id},
        ).one()
    return int(row[0]), int(row[1]), int(row[2])


def _cutoff(engine: Engine) -> datetime:
    with engine.connect() as conn:
        value: datetime = prune.cutoff(conn, _CUTOFF_DAYS)
    return value


def test_apply_deletes_only_old_unlinked_full_text_snapshots(
    engine: Engine, seeder: _Seeder, capsys: pytest.CaptureFixture[str]
) -> None:
    unlinked = seeder.snapshot()
    unlinked_too = seeder.snapshot()
    envelope = seeder.snapshot(basis="abstract_only", chunks=1)
    linked_full = seeder.snapshot()
    seeder.link(envelope=envelope, full_text=linked_full)
    linked_as_source = seeder.snapshot()
    seeder.link(envelope=linked_as_source)
    young = seeder.snapshot(age_days=_CUTOFF_DAYS - 10)
    lonely_envelope = seeder.snapshot(basis="abstract_only", chunks=1)

    assert (
        prune.run(engine, older_than_days=_CUTOFF_DAYS, batch_size=1, apply=True) == 0
    )

    assert _counts(engine, unlinked) == (0, 0, 0)
    assert _counts(engine, unlinked_too) == (0, 0, 0)
    assert _counts(engine, linked_full) == (1, 2, 2)
    assert _counts(engine, linked_as_source) == (1, 2, 2)
    assert _counts(engine, young) == (1, 2, 2)
    assert _counts(engine, envelope) == (1, 1, 1)
    assert _counts(engine, lonely_envelope) == (1, 1, 1)
    out = capsys.readouterr().out
    assert "batch 1: candidates=1 locked=1 deleted=1 kept=0 chunks=2 embeddings=2" in out
    assert "batch 2:" in out
    assert "batch 3:" not in out
    assert "total: deleted 2 snapshot(s), 4 chunk(s), 4 embedding(s); kept 0" in out


def test_dry_run_reports_the_count_and_deletes_nothing(
    engine: Engine, seeder: _Seeder, capsys: pytest.CaptureFixture[str]
) -> None:
    first = seeder.snapshot()
    second = seeder.snapshot(chunks=3)
    linked = seeder.snapshot()
    seeder.link(envelope=linked)

    assert prune.run(engine, older_than_days=_CUTOFF_DAYS) == 0

    out = capsys.readouterr().out
    assert "dry run: would delete 2 snapshot(s), 5 chunk(s), 5 embedding(s)" in out
    assert _counts(engine, first) == (1, 2, 2)
    assert _counts(engine, second) == (1, 3, 3)


@pytest.mark.parametrize(("days", "size"), [(0, 500), (-5, 500), (90, 0)])
def test_refuses_bad_flags(
    engine: Engine, capsys: pytest.CaptureFixture[str], days: int, size: int
) -> None:
    assert prune.run(engine, older_than_days=days, batch_size=size, apply=True) == 2
    assert "refusing" in capsys.readouterr().err


def test_a_link_committed_after_selection_is_caught_by_the_recheck(
    engine: Engine, seeder: _Seeder
) -> None:
    """The link lands between candidate selection and the lock; the re-check keeps it."""
    raced = seeder.snapshot()
    other = seeder.snapshot()
    envelope = seeder.snapshot(basis="abstract_only", chunks=0)

    def link_in(_conn: Connection, ids: list[uuid.UUID]) -> None:
        assert raced in ids
        with engine.begin() as racer:
            racer.execute(
                task_source_snapshot.insert().values(
                    **seeder.link_values(envelope=envelope, full_text=raced)
                )
            )

    result = prune.prune_batch(engine, _cutoff(engine), None, 10, before_lock=link_in)

    assert result.candidates == 2
    assert result.locked == 2
    assert result.deleted == [other]
    assert _counts(engine, raced) == (1, 2, 2)
    assert _counts(engine, other) == (0, 0, 0)


def test_a_link_in_flight_at_lock_time_makes_the_snapshot_skipped(
    engine: Engine, seeder: _Seeder
) -> None:
    """An uncommitted link holds a key lock on the snapshot; SKIP LOCKED passes it by."""
    raced = seeder.snapshot()
    other = seeder.snapshot()
    envelope = seeder.snapshot(basis="abstract_only", chunks=0)
    racer = engine.connect()
    racer_tx = racer.begin()
    try:

        def link_in(_conn: Connection, ids: list[uuid.UUID]) -> None:
            assert raced in ids
            racer.execute(
                task_source_snapshot.insert().values(
                    **seeder.link_values(envelope=envelope, full_text=raced)
                )
            )

        result = prune.prune_batch(engine, _cutoff(engine), None, 10, before_lock=link_in)
        racer_tx.commit()
    finally:
        racer.close()

    assert result.candidates == 2
    assert result.locked == 1
    assert result.deleted == [other]
    assert _counts(engine, raced) == (1, 2, 2)
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT count(*) FROM task_source_snapshot WHERE full_text_snapshot_id = :s"),
            {"s": raced},
        ).scalar_one() == 1


def test_a_link_attempted_after_the_lock_waits_and_cannot_commit_first(
    engine: Engine, seeder: _Seeder
) -> None:
    """Once the batch holds the lock, a racing link blocks; it can never slip under the re-check.

    The racer sets a short lock timeout so the test does not hang: its insert times
    out waiting on the batch's row lock, the batch then deletes the snapshot, and no
    link row is left pointing at a missing snapshot.
    """
    raced = seeder.snapshot()
    envelope = seeder.snapshot(basis="abstract_only", chunks=0)
    attempts: list[str] = []

    def link_in(_conn: Connection, locked: list[uuid.UUID]) -> None:
        assert raced in locked
        with engine.connect() as racer:
            with pytest.raises(OperationalError, match="lock timeout"), racer.begin():
                racer.execute(text("SET LOCAL lock_timeout = '300ms'"))
                racer.execute(
                    task_source_snapshot.insert().values(
                        **seeder.link_values(envelope=envelope, full_text=raced)
                    )
                )
            attempts.append("blocked")

    result = prune.prune_batch(engine, _cutoff(engine), None, 10, after_lock=link_in)

    assert attempts == ["blocked"]
    assert result.deleted == [raced]
    assert _counts(engine, raced) == (0, 0, 0)
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT count(*) FROM task_source_snapshot WHERE full_text_snapshot_id = :s"),
            {"s": raced},
        ).scalar_one() == 0
