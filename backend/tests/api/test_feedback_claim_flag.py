"""In-app feedback routes for element D: the ``claim_flag`` kind.

The integration test posts a flag, then asserts the Postgres row and the
Langfuse score call on a fake client.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from policy_atlas.core.schema import addressable_unit, annotation, block, chunk, citation
from tests.api.resource_support import create_task
from tests.api.test_feedback import URL, _row, _seed_report, feedback_client
from tests.helpers import now, seed_source

JUDGE = {
    "verdict": "tier_2",
    "weakly_grounded": False,
    "rationale": "The quote supports the direction, not the size.",
    "judge_model": "judge-model-1",
    "judge_prompt_version": "v7",
}


def _seed_claim(engine: Engine, seeded: dict[str, str]) -> dict[str, Any]:
    """Give the seeded report one claim with two citations and a judge verdict."""
    task_id = uuid.UUID(seeded["task_id"])
    ids = {name: uuid.uuid4() for name in ("block", "claim", "annotation")}
    citation_ids = [uuid.uuid4(), uuid.uuid4()]
    with engine.begin() as conn:
        conn.execute(
            block.insert().values(
                block_id=ids["block"],
                artefact_id=uuid.UUID(seeded["artefact_id"]),
                content="Breakfast clubs raise attendance.",
                content_hash="hash",
                created_at=now(),
            )
        )
        conn.execute(
            addressable_unit.insert().values(
                unit_id=ids["claim"],
                block_id=ids["block"],
                unit_type="text_span",
                locator={"start": 0, "end": 33},
                content="Breakfast clubs raise attendance.",
                created_at=now(),
            )
        )
        conn.execute(
            annotation.insert().values(
                annotation_id=ids["annotation"],
                block_id=ids["block"],
                unit_id=ids["claim"],
                annotation_type="citation",
                # The judge's verdict, with a key that a flag does not copy.
                payload={**JUDGE, "envelope_version": "e1"},
                created_at=now(),
            )
        )
        for citation_id in citation_ids:
            snapshot_id, _ = seed_source(conn, task_id, {"title": "A source"})
            chunk_id = uuid.uuid4()
            conn.execute(
                chunk.insert().values(
                    chunk_id=chunk_id,
                    source_snapshot_id=snapshot_id,
                    sequence=0,
                    content="Evidence.",
                    content_hash="hash",
                    locator={},
                    segmentation_policy="manual_v1",
                    created_at=now(),
                )
            )
            conn.execute(
                citation.insert().values(
                    citation_id=citation_id,
                    annotation_id=ids["annotation"],
                    chunk_id=chunk_id,
                    quote="Evidence.",
                    verification_result="pass",
                    created_at=now(),
                )
            )
    return {
        "claim_id": str(ids["claim"]),
        "block_id": str(ids["block"]),
        "citation_ids": sorted(str(citation_id) for citation_id in citation_ids),
    }


def _flag(seeded: dict[str, str], claim: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Build a claim flag body."""
    return {
        "kind": "claim_flag",
        "surface": "report_claim_sidebar",
        "task_id": seeded["task_id"],
        "artefact_id": seeded["artefact_id"],
        "claim_id": claim["claim_id"],
        "reason": "overstated",
        **overrides,
    }


def test_a_claim_flag_is_stored_with_the_judge_verdict_and_mirrored(
    tmp_path: Path, engine: Engine
) -> None:
    """Kind ``claim_flag``: the row holds the claim's citations, tier and verdict."""
    with feedback_client(tmp_path, "claim_flag") as (client, owner, _other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        claim = _seed_claim(engine, seeded)
        failing = claim["citation_ids"][0]
        body = _flag(
            seeded,
            claim,
            reason="unsupported",
            failing_citation_ids=[failing],
            # A viewed id that is not a citation of the claim is left out.
            provenance_viewed=[*claim["citation_ids"], str(uuid.uuid4())],
            note="The quote is about lunch clubs.",
        )

        response = client.post(URL, headers=owner, json=body)

        assert response.status_code == 201, response.text
        event_id = response.json()["feedback_event_id"]
        row = _row(engine, event_id)
        assert (row["surface"], row["kind"]) == ("report_claim_sidebar", "claim_flag")
        assert (row["target_type"], row["target_id"]) == ("claim", claim["claim_id"])
        assert str(row["capability_run_id"]) == seeded["run_id"]
        assert row["trace_id"] == "trace-synthesise"
        payload = dict(row["payload"])
        assert sorted(payload.pop("provenance_viewed")) == claim["citation_ids"]
        assert payload == {
            "reason": "unsupported",
            "failing_citation_ids": [failing],
            "note": "The quote is about lunch clubs.",
            "section_id": claim["block_id"],
            "citation_ids": claim["citation_ids"],
            "claim_tier": "tier_2",
            "judge_verdict": JUDGE,
        }
        score = langfuse.scores[0]
        assert (score["name"], score["value"], score["data_type"]) == (
            "claim_flag",
            "unsupported",
            "CATEGORICAL",
        )
        assert score["score_id"] == event_id
        assert score["trace_id"] == "trace-synthesise"
        assert score["comment"] == "The quote is about lunch clubs."
        assert score["metadata"]["reason"] == "unsupported"
        assert score["metadata"]["failing_citation_ids"] == [failing]


def test_one_flag_per_user_and_claim_which_can_change_or_be_retracted(
    tmp_path: Path, engine: Engine
) -> None:
    """Re-opening a flagged claim finds the flag; a change replaces it; undo retracts it."""
    with feedback_client(tmp_path, "claim_flag") as (client, owner, _other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        claim = _seed_claim(engine, seeded)
        first = client.post(URL, headers=owner, json=_flag(seeded, claim)).json()

        second = client.post(URL, headers=owner, json=_flag(seeded, claim, reason="wrong")).json()

        assert _row(engine, first["feedback_event_id"])["retracted_at"] is not None
        assert langfuse.score_api.deleted == [first["feedback_event_id"]]
        params = {"task_id": seeded["task_id"], "kind": "claim_flag"}
        listing = client.get(URL, headers=owner, params=params).json()["data"]
        assert [(record["target_id"], record["payload"]["reason"]) for record in listing] == [
            (claim["claim_id"], "wrong")
        ]

        retracted = client.delete(f"{URL}/{second['feedback_event_id']}", headers=owner)
        assert retracted.status_code == 204
        assert client.get(URL, headers=owner, params=params).json()["data"] == []


def test_the_failing_citations_must_be_citations_of_the_claim(
    tmp_path: Path, engine: Engine
) -> None:
    """A subset rule, a required reason, and at least one tick for "unsupported"."""
    with feedback_client(tmp_path, "claim_flag") as (client, owner, other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        claim = _seed_claim(engine, seeded)

        def post(**overrides: Any) -> int:
            body = _flag(seeded, claim, **overrides)
            status_code: int = client.post(URL, headers=owner, json=body).status_code
            return status_code

        assert post(failing_citation_ids=[str(uuid.uuid4())]) == 422
        assert post(reason="unsupported") == 422
        assert post(reason=None) == 422
        assert post(reason="boring") == 422
        assert post(claim_id=str(uuid.uuid4())) == 404
        assert post(claim_id="live:section-1") == 422
        assert client.post(URL, headers=other, json=_flag(seeded, claim)).status_code == 404
        assert langfuse.scores == []


def test_a_claim_flag_is_off_without_its_flag(tmp_path: Path, engine: Engine) -> None:
    """With another element on, a claim flag is still a 404."""
    with feedback_client(tmp_path, "citation_flag") as (client, owner, _other, _langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        claim = _seed_claim(engine, seeded)

        assert client.post(URL, headers=owner, json=_flag(seeded, claim)).status_code == 404
