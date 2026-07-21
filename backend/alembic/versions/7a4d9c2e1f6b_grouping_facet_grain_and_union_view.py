"""grouping facet-grain payloads and finding reference UNION view

Task 022 Phase B: migrate ``grouping_result`` from one row-level facet to
facet-keyed JSONB payloads at group grain, rewrite persisted group-id consumers
to the facet-qualified id scheme, add the ICF ``context_label`` rider column,
and create the cross-kind finding reference read view.

Revision ID: 7a4d9c2e1f6b
Revises: 2f9d7e1c4a6b
Create Date: 2026-07-14 00:00:00.000000

"""
from collections.abc import Mapping, Sequence
from typing import Any, Union, cast

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7a4d9c2e1f6b"
down_revision: Union[str, None] = "2f9d7e1c4a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GROUPING_FACET_CHECK = "facet IN ('intervention', 'outcome', 'population')"


def upgrade() -> None:
    op.add_column(
        "implementation_context_finding",
        sa.Column("context_label", sa.Text(), nullable=True),
    )
    _rewrite_grouping_consumers(upgrade=True)
    _upgrade_grouping_payloads()
    op.drop_constraint("ck_grr_facet", "grouping_result", type_="check")
    op.drop_column("grouping_result", "facet")
    _create_finding_reference_union()


def downgrade() -> None:
    _drop_finding_reference_union()
    _refuse_multifacet_downgrade()
    op.add_column("grouping_result", sa.Column("facet", sa.Text(), nullable=True))
    _rewrite_grouping_consumers(upgrade=False)
    _downgrade_grouping_payloads()
    op.alter_column("grouping_result", "facet", nullable=False)
    op.create_check_constraint(
        "ck_grr_facet",
        "grouping_result",
        _GROUPING_FACET_CHECK,
    )
    op.drop_column("implementation_context_finding", "context_label")


def _create_finding_reference_union() -> None:
    op.execute(
        """
        CREATE VIEW finding_reference_union AS
        SELECT
            finding_id,
            'iof'::text AS kind,
            extraction_record_id,
            project_id,
            intervention,
            outcome,
            population,
            setting,
            study_geography,
            study_design
        FROM intervention_outcome_finding
        UNION ALL
        SELECT
            finding_id,
            'icf'::text AS kind,
            extraction_record_id,
            project_id,
            intervention,
            outcome,
            population,
            setting,
            study_geography,
            study_design
        FROM implementation_context_finding
        """
    )


def _drop_finding_reference_union() -> None:
    op.execute("DROP VIEW IF EXISTS finding_reference_union")


def _upgrade_grouping_payloads() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT grouping_result_id, facet, groups, counts, flags, grouping_provenance
            FROM grouping_result
            ORDER BY grouping_result_id
            """
        )
    ).mappings()
    for row in rows:
        facet = cast("str", row["facet"])
        old_groups = _json_object(row["groups"])
        provenance = _json_object(row["grouping_provenance"])
        provenance["facets"] = [facet]
        bind.execute(
            _json_update_text(
                """
                UPDATE grouping_result
                SET groups = :groups,
                    counts = :counts,
                    flags = :flags,
                    grouping_provenance = :provenance
                WHERE grouping_result_id = :grouping_result_id
                """,
                "groups",
                "counts",
                "flags",
                "provenance",
            ),
            {
                "grouping_result_id": row["grouping_result_id"],
                "groups": _upgrade_groups_payload(old_groups, facet),
                "counts": {facet: row["counts"]},
                "flags": {facet: row["flags"]},
                "provenance": provenance,
            },
        )


def _downgrade_grouping_payloads() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT grouping_result_id, groups, counts, flags, grouping_provenance
            FROM grouping_result
            ORDER BY grouping_result_id
            """
        )
    ).mappings()
    for row in rows:
        groups_payload = _json_object(row["groups"])
        facets = _facet_keys(groups_payload)
        facet = facets[0] if facets else "intervention"
        old_groups = _downgrade_groups_payload(groups_payload, facet)
        provenance = _json_object(row["grouping_provenance"])
        provenance.pop("facets", None)
        counts = _json_object(row["counts"])
        flags = _json_object(row["flags"])
        bind.execute(
            _json_update_text(
                """
                UPDATE grouping_result
                SET facet = :facet,
                    groups = :groups,
                    counts = :counts,
                    flags = :flags,
                    grouping_provenance = :provenance
                WHERE grouping_result_id = :grouping_result_id
                """,
                "groups",
                "counts",
                "flags",
                "provenance",
            ),
            {
                "grouping_result_id": row["grouping_result_id"],
                "facet": facet,
                "groups": old_groups,
                "counts": counts.get(facet, {}),
                "flags": flags.get(facet, []),
                "provenance": provenance,
            },
        )


def _rewrite_grouping_consumers(*, upgrade: bool) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT synthesis_result_id, evidence_scope_id, grouping_run_id, blocks
            FROM synthesis_result
            WHERE grouping_run_id IS NOT NULL
            ORDER BY synthesis_result_id
            """
        )
    ).mappings()
    for row in rows:
        grouping = _grouping_row_for_synthesis(
            row["evidence_scope_id"],
            row["grouping_run_id"],
        )
        if grouping is None:
            continue
        mapping = (
            _upgrade_reference_map(grouping)
            if upgrade
            else _downgrade_reference_map(grouping)
        )
        if not mapping:
            continue
        blocks = _rewrite_group_ids(row["blocks"], mapping)
        bind.execute(
            _json_update_text(
                """
                UPDATE synthesis_result
                SET blocks = :blocks
                WHERE synthesis_result_id = :synthesis_result_id
                """,
                "blocks",
            ),
            {"synthesis_result_id": row["synthesis_result_id"], "blocks": blocks},
        )
        _rewrite_theme_annotations(row["blocks"], mapping)


def _grouping_row_for_synthesis(
    evidence_scope_id: Any, grouping_run_id: Any
) -> Mapping[str, Any] | None:
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            """
            SELECT facet, groups
            FROM grouping_result
            WHERE evidence_scope_id = :evidence_scope_id
            AND run_id = :grouping_run_id
            """
        ),
        {
            "evidence_scope_id": evidence_scope_id,
            "grouping_run_id": grouping_run_id,
        },
    ).mappings().first()
    return row


def _rewrite_theme_annotations(blocks: Any, mapping: Mapping[str, str]) -> None:
    block_ids = _block_ids(blocks)
    if not block_ids:
        return
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT annotation_id, payload
            FROM annotation
            WHERE annotation_type = 'theme'
            AND block_id::text IN :block_ids
            ORDER BY annotation_id
            """
        ).bindparams(sa.bindparam("block_ids", expanding=True)),
        {"block_ids": tuple(block_ids)},
    ).mappings()
    for row in rows:
        payload = _rewrite_theme_payload(row["payload"], mapping)
        bind.execute(
            _json_update_text(
                """
                UPDATE annotation
                SET payload = :payload
                WHERE annotation_id = :annotation_id
                """,
                "payload",
            ),
            {"annotation_id": row["annotation_id"], "payload": payload},
        )


def _upgrade_groups_payload(payload: Mapping[str, Any], facet: str) -> dict[str, Any]:
    facet_payload = dict(payload)
    facet_payload["groups"] = [
        _upgrade_group_object(group, facet=facet, index=index)
        for index, group in enumerate(_groups(payload), start=1)
    ]
    return {facet: facet_payload}


def _downgrade_groups_payload(payload: Mapping[str, Any], facet: str) -> dict[str, Any]:
    facet_payload = _json_object(payload.get(facet))
    old_payload = dict(facet_payload)
    old_payload["groups"] = [
        _downgrade_group_object(group) for group in _groups(facet_payload)
    ]
    return old_payload


def _upgrade_group_object(group: Mapping[str, Any], *, facet: str, index: int) -> dict[str, Any]:
    upgraded = dict(group)
    qualified = _qualified_group_id(facet, index)
    legacy_group_id = upgraded.get("group_id")
    if isinstance(legacy_group_id, str) and legacy_group_id and legacy_group_id != qualified:
        upgraded["legacy_group_id"] = legacy_group_id
    legacy_facet = upgraded.get("facet")
    if isinstance(legacy_facet, str) and legacy_facet and legacy_facet != facet:
        upgraded["legacy_facet"] = legacy_facet
    upgraded["group_id"] = qualified
    upgraded["facet"] = facet
    return upgraded


def _downgrade_group_object(group: Mapping[str, Any]) -> dict[str, Any]:
    downgraded = dict(group)
    legacy_group_id = downgraded.pop("legacy_group_id", None)
    legacy_facet = downgraded.pop("legacy_facet", None)
    downgraded.pop("group_id", None)
    downgraded.pop("facet", None)
    if isinstance(legacy_group_id, str) and legacy_group_id:
        downgraded["group_id"] = legacy_group_id
    if isinstance(legacy_facet, str) and legacy_facet:
        downgraded["facet"] = legacy_facet
    return downgraded


def _upgrade_reference_map(grouping: Mapping[str, Any]) -> dict[str, str]:
    facet = grouping.get("facet")
    if not isinstance(facet, str) or not facet:
        return {}
    payload = _json_object(grouping.get("groups"))
    mapping: dict[str, str] = {}
    for index, group in enumerate(_groups(payload), start=1):
        qualified = _qualified_group_id(facet, index)
        for key in ("group_id", "id", "label"):
            value = group.get(key)
            if isinstance(value, str) and value:
                mapping.setdefault(value, qualified)
        for value in (str(index), f"g{index}", f"g{index:02d}"):
            mapping.setdefault(value, qualified)
    return mapping


def _downgrade_reference_map(grouping: Mapping[str, Any]) -> dict[str, str]:
    payload = _json_object(grouping.get("groups"))
    mapping: dict[str, str] = {}
    for facet in _facet_keys(payload):
        facet_payload = _json_object(payload.get(facet))
        for index, group in enumerate(_groups(facet_payload), start=1):
            qualified = _group_string(group.get("group_id")) or _qualified_group_id(
                facet, index
            )
            old_ref = (
                _group_string(group.get("label"))
                or _group_string(group.get("legacy_group_id"))
                or _group_string(group.get("id"))
                or f"g{index}"
            )
            mapping[qualified] = old_ref
    return mapping


def _rewrite_group_ids(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, list):
        return [_rewrite_group_ids(item, mapping) for item in value]
    if isinstance(value, dict):
        rewritten: dict[str, Any] = {}
        for key, item in value.items():
            if key == "group_ids" and isinstance(item, list):
                rewritten[key] = [
                    mapping.get(group_id, group_id) if isinstance(group_id, str) else group_id
                    for group_id in item
                ]
            else:
                rewritten[key] = _rewrite_group_ids(item, mapping)
        return rewritten
    return value


def _rewrite_theme_payload(payload: Any, mapping: Mapping[str, str]) -> Any:
    if not isinstance(payload, dict):
        return payload
    rewritten = dict(payload)
    theme = rewritten.get("theme")
    if not isinstance(theme, dict) or theme.get("source") != "grouping":
        return rewritten
    theme_rewritten = dict(theme)
    referenced_ids = theme_rewritten.get("referenced_ids")
    if isinstance(referenced_ids, list):
        theme_rewritten["referenced_ids"] = _rewrite_id_list(referenced_ids, mapping)
    rewritten["theme"] = theme_rewritten
    cited_ids = rewritten.get("cited_ids")
    if isinstance(cited_ids, list):
        rewritten["cited_ids"] = _rewrite_id_list(cited_ids, mapping)
    return rewritten


def _rewrite_id_list(values: list[Any], mapping: Mapping[str, str]) -> list[Any]:
    return [mapping.get(value, value) if isinstance(value, str) else value for value in values]


def _refuse_multifacet_downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT grouping_result_id, groups
            FROM grouping_result
            ORDER BY grouping_result_id
            """
        )
    ).mappings()
    for row in rows:
        facet_count = len(_facet_keys(_json_object(row["groups"])))
        if facet_count > 1:
            raise RuntimeError(
                "cannot downgrade grouping_result with multi-facet groups payload; "
                "the one-facet schema cannot represent more than one facet key"
            )


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _groups(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_groups = payload.get("groups")
    if not isinstance(raw_groups, list):
        return []
    return [group for group in raw_groups if isinstance(group, dict)]


def _facet_keys(payload: Mapping[str, Any]) -> list[str]:
    return [
        key
        for key, value in payload.items()
        if isinstance(key, str) and isinstance(value, dict) and isinstance(value.get("groups"), list)
    ]


def _block_ids(blocks: Any) -> list[str]:
    if not isinstance(blocks, list):
        return []
    ids: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_id = block.get("block_id")
        if isinstance(block_id, str) and block_id:
            ids.append(block_id)
    return ids


def _qualified_group_id(facet: str, index: int) -> str:
    return f"{facet}:g{index:02d}"


def _group_string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _json_update_text(sql: str, *json_params: str) -> Any:
    clause = sa.text(sql)
    return clause.bindparams(
        *(sa.bindparam(name, type_=postgresql.JSONB()) for name in json_params)
    )
