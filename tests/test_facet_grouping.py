from __future__ import annotations

import pytest

from policy_atlas.facet_grouping import (
    FacetValueRecord,
    OpenAIFacetGroupingBackend,
    StubFacetGroupingBackend,
    build_partition_messages,
    build_repair_messages,
)


def _values() -> list[FacetValueRecord]:
    return [
        {
            "id": "v1",
            "value": "Housing First",
            "finding_count": 2,
            "counterparts": ["rough sleeping"],
        },
        {
            "id": "v2",
            "value": "housing support",
            "finding_count": 1,
            "counterparts": ["tenancy sustainment"],
        },
        {
            "id": "v3",
            "value": "Rapid rehousing",
            "finding_count": 1,
            "counterparts": ["homelessness duration"],
        },
        {
            "id": "v4",
            "value": "stubungroupable complex blended intervention",
            "finding_count": 1,
            "counterparts": ["mixed outcomes"],
        },
    ]


def test_stub_facet_grouping_is_deterministic_and_covers_group_shapes() -> None:
    backend = StubFacetGroupingBackend()

    expected = {
        "groups": [
            {
                "label": "housing",
                "description": "Values grouped by stub token 'housing'",
                "member_ids": ["v1", "v2"],
            },
            {
                "label": "rapid",
                "description": "Values grouped by stub token 'rapid'",
                "member_ids": ["v3"],
            },
        ],
        "ungroupable": ["v4"],
    }

    assert backend.mode == "stub"
    assert backend.partition(_values(), facet="intervention") == expected
    assert backend.partition(_values(), facet="intervention") == expected
    assert (
        backend.repair(
            _values(),
            facet="intervention",
            accepted_groups=[
                {
                    "label": "accepted",
                    "description": "Ignored by the stub.",
                    "member_ids": ["old"],
                }
            ],
        )
        == expected
    )


def test_stub_facet_grouping_failure_sentinel() -> None:
    backend = StubFacetGroupingBackend(fail=True)

    with pytest.raises(RuntimeError, match="Stub facet grouping failure sentinel."):
        backend.partition(_values(), facet="intervention")
    with pytest.raises(RuntimeError, match="Stub facet grouping failure sentinel."):
        backend.repair(_values(), facet="intervention", accepted_groups=[])


def test_openai_facet_grouping_backend_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert OpenAIFacetGroupingBackend(api_key="sk-test").mode == "live"
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIFacetGroupingBackend()


def test_repair_and_partition_share_prompt_surface() -> None:
    partition_messages = build_partition_messages(_values(), facet="outcome")
    repair_messages = build_repair_messages(
        _values(),
        facet="outcome",
        accepted_groups=[
            {
                "label": "Housing",
                "description": "Housing interventions.",
                "member_ids": ["v1", "v2"],
            }
        ],
    )

    assert repair_messages[0]["content"] == partition_messages[0]["content"]
    system_prompt = str(partition_messages[0]["content"])
    assert "ungroupable" in system_prompt
    assert "Miscellaneous" in system_prompt
    assert "never whether it worked" in system_prompt
    assert "{intent}" not in system_prompt
    assert "{scope_intent}" not in system_prompt
    assert "scope intent" not in system_prompt.casefold()
