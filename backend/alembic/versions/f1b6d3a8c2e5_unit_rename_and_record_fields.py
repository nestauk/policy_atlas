"""task 046 amendment 3 — ``population`` becomes ``unit``; two record fields

The amendment's one revision (amendment-3-final § 2.11; R71, R73, R75). It
reaches production data (Evidence search is live), so every step is a plain
rename or an additive column: no finding row changes value and no version on
the finding records changes, so nothing is extracted again.

Upgrade
    ``intervention_profile_record``     adds nullable text ``programme_name``
                                        and ``study_country`` (null on every
                                        existing row); renames ``population``
                                        → ``unit`` and ``population_tag`` →
                                        ``unit_tag``, with its check
                                        ``ck_ipr_population_tag`` →
                                        ``ck_ipr_unit_tag`` (same values).
    ``intervention_outcome_finding``    ``population`` → ``unit``.
    ``implementation_context_finding``  ``population`` → ``unit``.
    ``finding_reference_union``         dropped and recreated with ``unit``
                                        (``core/schema.py``'s
                                        ``FINDING_REFERENCE_UNION_SQL``).
    The grouping facet ``"population"`` → ``"unit"`` in every stored place
    (Q26: no reader keeps an alias). Only rows holding the old value are
    touched; list order is kept; everything else in a row stays as it was.

    ``plan.payload``                    ``grouping_facets[]``; and each
                                        ``steer_point_defaults[].delta.group
                                        .grouping`` (``facets[]`` or ``facet``).
    ``grouping_result.groups``          the top-level key; inside it, each
                                        ``groups[].group_id`` prefix
                                        ``population:`` → ``unit:`` and each
                                        ``groups[].facet``.
    ``grouping_result.counts``,         the top-level key (both are keyed by
    ``grouping_result.flags``           facet, as ``groups`` is).
    ``grouping_result
    .grouping_provenance``              ``facet``, ``facets[]`` and the key of
                                        ``facet_runs``.
    ``annotation.payload``              ``theme.referenced_ids[]`` when
                                        ``theme.source`` is ``grouping``, and
                                        ``pattern.group_id``: the id prefix.
    ``synthesis_result.blocks``         ``[].group_ids[]``: the id prefix.

    A group id is ``<facet>:gNN`` and its prefix must equal its payload key
    (``synthesis_tools.py`` ``_grouping_summary``, ``synthesise.py``
    ``_required_group_id``), so the ids move with the key, and so does every
    stored reference to them.

Downgrade
    Writes ``"population"`` / ``population:`` back into every place above, drops the
    view, reverses the three renames and the check's name, recreates the view
    as it stood at ``e9a4c1f7b3d2`` and drops the two new columns (their
    values are lost; nothing else references them).

Revision ID: f1b6d3a8c2e5
Revises: e9a4c1f7b3d2
Create Date: 2026-09-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from policy_atlas.core.schema import FINDING_REFERENCE_UNION_SQL

revision: str = "f1b6d3a8c2e5"
down_revision: Union[str, None] = "e9a4c1f7b3d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_IPR = "intervention_profile_record"
_FINDING_TABLES = ("intervention_outcome_finding", "implementation_context_finding")

# Frozen here, not imported: the check must keep meaning what it meant.
_UNIT_TAGS = "('on_target', 'adjacent', 'other')"

#: The three-branch view as it stood at ``e9a4c1f7b3d2`` — frozen here, because
#: the downgrade must restore exactly that, whatever ``schema.py`` says later.
_POPULATION_UNION_SQL = """
CREATE VIEW finding_reference_union AS
SELECT
    finding_id,
    'iof'::text AS kind,
    extraction_record_id,
    task_id,
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
    task_id,
    intervention,
    outcome,
    population,
    setting,
    study_geography,
    study_design
FROM implementation_context_finding
UNION ALL
SELECT
    record_id AS finding_id,
    'interventions'::text AS kind,
    extraction_record_id,
    task_id,
    intervention,
    outcome,
    population,
    setting,
    study_geography,
    study_design
FROM intervention_profile_record
"""

# --- The facet-key data migration (plain SQL, session-local helpers) ---------
#
# ``pg_temp`` functions live only for this migration's connection. Each maps
# one JSON value and returns it unchanged unless it holds ``old`` (a facet
# value) or an id with the prefix ``old:``.

_HELPERS_SQL = (
    # A text id with the prefix ``old:`` takes the prefix ``new:``.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_swap_id(value text, old text, new text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN left(value, length(old) + 1) = old || ':'
        THEN new || substr(value, length(old) + 1)
        ELSE value
    END
$$
""",
    # Whether a JSON array holds an id with the prefix ``old:``.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_has_id(value jsonb, old text)
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(value) = 'array' THEN EXISTS (
            SELECT 1 FROM jsonb_array_elements(value) AS e(item)
            WHERE jsonb_typeof(item) = 'string'
            AND left(item #>> '{}', length(old) + 1) = old || ':'
        )
        ELSE false
    END
$$
""",
    # Each string id of a JSON array through ``pa_swap_id``.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_swap_id_list(value jsonb, old text, new text)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(value) = 'array' THEN COALESCE(
            (
                SELECT jsonb_agg(
                    CASE WHEN jsonb_typeof(item) = 'string'
                        THEN to_jsonb(pg_temp.pa_swap_id(item #>> '{}', old, new))
                        ELSE item
                    END
                    ORDER BY position
                )
                FROM jsonb_array_elements(value) WITH ORDINALITY AS e(item, position)
            ),
            '[]'::jsonb
        )
        ELSE value
    END
$$
""",
    # A facet list: the element ``old`` becomes ``new``.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_swap_facet_list(value jsonb, old text, new text)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(value) = 'array' THEN COALESCE(
            (
                SELECT jsonb_agg(
                    CASE WHEN item = to_jsonb(old) THEN to_jsonb(new) ELSE item END
                    ORDER BY position
                )
                FROM jsonb_array_elements(value) WITH ORDINALITY AS e(item, position)
            ),
            '[]'::jsonb
        )
        ELSE value
    END
$$
""",
    # An object keyed by facet: the key ``old`` becomes ``new``.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_swap_key(value jsonb, old text, new text)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(value) = 'object' AND value ? old
        THEN (value - old) || jsonb_build_object(new, value -> old)
        ELSE value
    END
$$
""",
    # An object carrying ``facet`` and/or ``facets`` (a grouping directive, or
    # the grouping provenance): both through the facet swap.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_swap_grouping(value jsonb, old text, new text)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(value) <> 'object' THEN value
        ELSE value
            || CASE WHEN value ? 'facets'
                THEN jsonb_build_object(
                    'facets', pg_temp.pa_swap_facet_list(value -> 'facets', old, new)
                )
                ELSE '{}'::jsonb END
            || CASE WHEN value -> 'facet' = to_jsonb(old)
                THEN jsonb_build_object('facet', new)
                ELSE '{}'::jsonb END
    END
$$
""",
    # One stored group record: ``group_id`` prefix and ``facet``.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_swap_group(value jsonb, old text, new text)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(value) <> 'object' THEN value
        ELSE value
            || CASE WHEN jsonb_typeof(value -> 'group_id') = 'string'
                THEN jsonb_build_object(
                    'group_id', pg_temp.pa_swap_id(value ->> 'group_id', old, new)
                )
                ELSE '{}'::jsonb END
            || CASE WHEN value -> 'facet' = to_jsonb(old)
                THEN jsonb_build_object('facet', new)
                ELSE '{}'::jsonb END
    END
$$
""",
    # ``grouping_result.groups``: the key, then the bucket's group records.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_swap_groups(value jsonb, old text, new text)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(value) = 'object' AND value ? old THEN
            (value - old) || jsonb_build_object(
                new,
                CASE
                    WHEN jsonb_typeof(value #> ARRAY[old, 'groups']) = 'array'
                    THEN jsonb_set(
                        value -> old,
                        '{groups}',
                        COALESCE(
                            (
                                SELECT jsonb_agg(
                                    pg_temp.pa_swap_group(item, old, new)
                                    ORDER BY position
                                )
                                FROM jsonb_array_elements(value #> ARRAY[old, 'groups'])
                                    WITH ORDINALITY AS e(item, position)
                            ),
                            '[]'::jsonb
                        )
                    )
                    ELSE value -> old
                END
            )
        ELSE value
    END
$$
""",
    # ``plan.payload.steer_point_defaults``: each rule's group delta.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_swap_steer_defaults(value jsonb, old text, new text)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(value) = 'array' THEN COALESCE(
            (
                SELECT jsonb_agg(
                    CASE
                        WHEN jsonb_typeof(item #> '{delta,group,grouping}') = 'object'
                        THEN jsonb_set(
                            item,
                            '{delta,group,grouping}',
                            pg_temp.pa_swap_grouping(item #> '{delta,group,grouping}', old, new)
                        )
                        ELSE item
                    END
                    ORDER BY position
                )
                FROM jsonb_array_elements(value) WITH ORDINALITY AS e(item, position)
            ),
            '[]'::jsonb
        )
        ELSE value
    END
$$
""",
    # ``synthesis_result.blocks``: each section spec's ``group_ids``.
    """
CREATE OR REPLACE FUNCTION pg_temp.pa_swap_blocks(value jsonb, old text, new text)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(value) = 'array' THEN COALESCE(
            (
                SELECT jsonb_agg(
                    CASE
                        WHEN pg_temp.pa_has_id(item -> 'group_ids', old)
                        THEN jsonb_set(
                            item,
                            '{group_ids}',
                            pg_temp.pa_swap_id_list(item -> 'group_ids', old, new)
                        )
                        ELSE item
                    END
                    ORDER BY position
                )
                FROM jsonb_array_elements(value) WITH ORDINALITY AS e(item, position)
            ),
            '[]'::jsonb
        )
        ELSE value
    END
$$
""",
)

_DROP_HELPERS_SQL = tuple(
    f"DROP FUNCTION IF EXISTS pg_temp.{name}({args})"
    for name, args in (
        ("pa_swap_blocks", "jsonb, text, text"),
        ("pa_swap_steer_defaults", "jsonb, text, text"),
        ("pa_swap_groups", "jsonb, text, text"),
        ("pa_swap_group", "jsonb, text, text"),
        ("pa_swap_grouping", "jsonb, text, text"),
        ("pa_swap_key", "jsonb, text, text"),
        ("pa_swap_facet_list", "jsonb, text, text"),
        ("pa_swap_id_list", "jsonb, text, text"),
        ("pa_has_id", "jsonb, text"),
        ("pa_swap_id", "text, text, text"),
    )
)

#: One UPDATE per stored place; each ``WHERE`` selects only rows holding the
#: old value, so no other row is rewritten.
_REWRITES_SQL = (
    # plan.payload.grouping_facets[]
    "UPDATE plan SET payload = jsonb_set(payload, '{grouping_facets}', "
    "pg_temp.pa_swap_facet_list(payload -> 'grouping_facets', :old, :new)) "
    "WHERE jsonb_typeof(payload -> 'grouping_facets') = 'array' "
    "AND payload -> 'grouping_facets' ? :old",
    # plan.payload.steer_point_defaults[].delta.group.grouping.{facets[],facet}
    "UPDATE plan SET payload = jsonb_set(payload, '{steer_point_defaults}', "
    "pg_temp.pa_swap_steer_defaults(payload -> 'steer_point_defaults', :old, :new)) "
    "WHERE jsonb_typeof(payload -> 'steer_point_defaults') = 'array' "
    "AND EXISTS ("
    "  SELECT 1 FROM jsonb_array_elements(payload -> 'steer_point_defaults') AS d(item)"
    "  WHERE item #> '{delta,group,grouping,facet}' = to_jsonb(CAST(:old AS text))"
    "  OR (jsonb_typeof(item #> '{delta,group,grouping,facets}') = 'array'"
    "      AND item #> '{delta,group,grouping,facets}' ? :old)"
    ")",
    # grouping_result.groups: key, groups[].group_id prefix, groups[].facet
    "UPDATE grouping_result SET groups = pg_temp.pa_swap_groups(groups, :old, :new) "
    "WHERE jsonb_typeof(groups) = 'object' AND groups ? :old",
    # grouping_result.counts / flags: key
    "UPDATE grouping_result SET counts = pg_temp.pa_swap_key(counts, :old, :new) "
    "WHERE jsonb_typeof(counts) = 'object' AND counts ? :old",
    "UPDATE grouping_result SET flags = pg_temp.pa_swap_key(flags, :old, :new) "
    "WHERE jsonb_typeof(flags) = 'object' AND flags ? :old",
    # grouping_result.grouping_provenance: facet, facets[], facet_runs key
    "UPDATE grouping_result SET grouping_provenance = jsonb_set("
    "pg_temp.pa_swap_grouping(grouping_provenance, :old, :new), '{facet_runs}', "
    "pg_temp.pa_swap_key(grouping_provenance -> 'facet_runs', :old, :new)) "
    "WHERE jsonb_typeof(grouping_provenance -> 'facet_runs') = 'object' "
    "AND (grouping_provenance -> 'facet' = to_jsonb(CAST(:old AS text)) "
    "  OR (jsonb_typeof(grouping_provenance -> 'facets') = 'array' "
    "      AND grouping_provenance -> 'facets' ? :old) "
    "  OR grouping_provenance -> 'facet_runs' ? :old)",
    # annotation.payload.theme.referenced_ids[] (grouping source): id prefix
    "UPDATE annotation SET payload = jsonb_set(payload, '{theme,referenced_ids}', "
    "pg_temp.pa_swap_id_list(payload #> '{theme,referenced_ids}', :old, :new)) "
    "WHERE payload #>> '{theme,source}' = 'grouping' "
    "AND pg_temp.pa_has_id(payload #> '{theme,referenced_ids}', :old)",
    # annotation.payload.pattern.group_id: id prefix
    "UPDATE annotation SET payload = jsonb_set(payload, '{pattern,group_id}', "
    "to_jsonb(pg_temp.pa_swap_id(payload #>> '{pattern,group_id}', :old, :new))) "
    "WHERE jsonb_typeof(payload #> '{pattern,group_id}') = 'string' "
    "AND left(payload #>> '{pattern,group_id}', length(:old) + 1) = :old || ':'",
    # synthesis_result.blocks[].group_ids[]: id prefix
    "UPDATE synthesis_result SET blocks = pg_temp.pa_swap_blocks(blocks, :old, :new) "
    "WHERE jsonb_typeof(blocks) = 'array' AND EXISTS ("
    "  SELECT 1 FROM jsonb_array_elements(blocks) AS b(item)"
    "  WHERE pg_temp.pa_has_id(item -> 'group_ids', :old)"
    ")",
)


def _swap_facet(old: str, new: str) -> None:
    """Rewrite the grouping facet ``old`` → ``new`` in every stored place.

    Args:
        old: The facet value to replace (a fixed identifier, never user text).
        new: The facet value to write.
    """
    for statement in _HELPERS_SQL:
        op.execute(statement)
    bind = op.get_bind()
    for statement in _REWRITES_SQL:
        bind.execute(sa.text(statement).bindparams(old=old, new=new))
    for statement in _DROP_HELPERS_SQL:
        op.execute(statement)


def upgrade() -> None:
    op.add_column(_IPR, sa.Column("programme_name", sa.Text(), nullable=True))
    op.add_column(_IPR, sa.Column("study_country", sa.Text(), nullable=True))

    # The view names the renamed columns, so it goes first and comes back last.
    op.execute("DROP VIEW finding_reference_union")
    op.alter_column(_IPR, "population", new_column_name="unit")
    op.alter_column(_IPR, "population_tag", new_column_name="unit_tag")
    op.drop_constraint("ck_ipr_population_tag", _IPR, type_="check")
    op.create_check_constraint(
        "ck_ipr_unit_tag",
        _IPR,
        f"unit_tag IS NULL OR unit_tag IN {_UNIT_TAGS}",
    )
    for table in _FINDING_TABLES:
        op.alter_column(table, "population", new_column_name="unit")
    op.execute(FINDING_REFERENCE_UNION_SQL)

    _swap_facet("population", "unit")


def downgrade() -> None:
    _swap_facet("unit", "population")

    op.execute("DROP VIEW finding_reference_union")
    for table in _FINDING_TABLES:
        op.alter_column(table, "unit", new_column_name="population")
    op.drop_constraint("ck_ipr_unit_tag", _IPR, type_="check")
    op.alter_column(_IPR, "unit_tag", new_column_name="population_tag")
    op.create_check_constraint(
        "ck_ipr_population_tag",
        _IPR,
        f"population_tag IS NULL OR population_tag IN {_UNIT_TAGS}",
    )
    op.alter_column(_IPR, "unit", new_column_name="population")
    op.execute(_POPULATION_UNION_SQL)

    op.drop_column(_IPR, "study_country")
    op.drop_column(_IPR, "programme_name")
