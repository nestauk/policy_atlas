"""screen step-name vocabulary rename (task 019 Phase D lane 2, item 12)

Renames the plan-vocabulary step names screen -> screen_abstract (the
mandatory spine's stage-1 pass) and screen_stage2 -> screen_full (the
discretionary stage-2 full-text re-screen). The DB stores the actual
screening stage as an integer (source_screening_result.screen_stage) and the
harness registry component stays "screen" (both steps dispatch to it) — this
migration touches only the plan-vocabulary strings persisted for the
orchestration plan and its run events:

1. ``orchestration_plan.payload`` (the validated ``OrchestrationPlan`` dump):
   - the ``components`` JSONB array's ``"screen_stage2"`` element
   - the ``component_rationale`` JSONB object's ``"screen_stage2"`` key
   ("screen" never appears in ``payload`` — it is the mandatory spine, never
   a discretionary component, so it is never persisted in these fields.)

2. ``event_log.payload`` for the three event types whose payload carries the
   plan step name under the ``"component"`` key (``run.started``,
   ``plan.compiled``, ``component.timing`` — see runner.py's
   ``_run_step_attempt`` / ``_plan_compiled_payload`` / ``_record_component_
   timing``): ``"screen"`` -> ``"screen_abstract"``, ``"screen_stage2"`` ->
   ``"screen_full"``. ``component.started`` / ``component.completed`` /
   ``component.failed`` (harness.py) always carry the *registry* component
   name ("screen"), never the discretionary step name "screen_stage2", and
   the registry name is unchanged by this rename — those event types are
   deliberately left untouched.

Every UPDATE is scoped to the exact JSONB key/element/event_type shapes
above via a WHERE clause proving the shape is present — never a blind text
replace across payloads (the word "screen" also appears in free text, e.g.
component_rationale sentences and steering intents, which must survive
unrewritten).

Revision ID: b7f3d9a2c5e1
Revises: 921d3a781f3f
Create Date: 2026-07-12 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7f3d9a2c5e1"
down_revision: Union[str, None] = "921d3a781f3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PLAN_EVENT_TYPES = "('run.started', 'plan.compiled', 'component.timing')"


def _rewrite_components_array(*, old: str, new: str) -> None:
    op.execute(
        f"""
        UPDATE orchestration_plan
        SET payload = jsonb_set(
            payload,
            '{{components}}',
            (
                SELECT jsonb_agg(
                    CASE WHEN elem = '"{old}"'::jsonb THEN '"{new}"'::jsonb ELSE elem END
                )
                FROM jsonb_array_elements(payload->'components') AS elem
            )
        )
        WHERE payload->'components' @> '["{old}"]'::jsonb
        """
    )


def _rewrite_component_rationale_key(*, old: str, new: str) -> None:
    op.execute(
        f"""
        UPDATE orchestration_plan
        SET payload = jsonb_set(
            payload,
            '{{component_rationale}}',
            ((payload->'component_rationale') - '{old}'::text)
                || jsonb_build_object('{new}', payload->'component_rationale'->'{old}')
        )
        WHERE payload->'component_rationale' ? '{old}'
        """
    )


def _rewrite_event_component(*, old: str, new: str) -> None:
    op.execute(
        f"""
        UPDATE event_log
        SET payload = jsonb_set(payload, '{{component}}', '"{new}"'::jsonb)
        WHERE event_type IN {_PLAN_EVENT_TYPES}
        AND payload->>'component' = '{old}'
        """
    )


def upgrade() -> None:
    _rewrite_components_array(old="screen_stage2", new="screen_full")
    _rewrite_component_rationale_key(old="screen_stage2", new="screen_full")
    _rewrite_event_component(old="screen", new="screen_abstract")
    _rewrite_event_component(old="screen_stage2", new="screen_full")


def downgrade() -> None:
    _rewrite_event_component(old="screen_full", new="screen_stage2")
    _rewrite_event_component(old="screen_abstract", new="screen")
    _rewrite_component_rationale_key(old="screen_full", new="screen_stage2")
    _rewrite_components_array(old="screen_full", new="screen_stage2")
