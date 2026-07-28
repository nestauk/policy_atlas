import { scrub } from "../../lib/scrub";
import type { ResolvedDecision } from "../../store";
import { Card } from "../../ui/brand/Card";
import { Chip } from "../../ui/brand/Chip";
import { friendlyDecisionDetails } from "../decisionsPresentation";
import { DECIDED_BY_LABEL, decisionProse } from "./checkInPresentation";

/**
 * The answered-state collapse (strand 4): a resolved check-in shrinks to its
 * decision echo — who decided, the friendly-labelled interpreted action, and
 * any typed prose. Raw option ids and raw params never render (the demo's
 * comma-separated id forms were placeholders, not ported).
 */
export function AnsweredCheckIn({ decision }: { decision: ResolvedDecision }) {
  const details = friendlyDecisionDetails(decision.response as Record<string, unknown>);
  const prose = decisionProse(decision);
  const decidedBy = decision.decidedBy !== null ? DECIDED_BY_LABEL[decision.decidedBy] : null;
  return (
    <Card className="anim-rise border-l-2 border-l-green px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone="green">Answered</Chip>
        {decidedBy !== undefined && decidedBy !== null && (
          <span className="text-[11.5px] text-grey">{decidedBy}</span>
        )}
      </div>
      {prose !== null && (
        <p className="mt-2 border-l-2 border-l-line pl-2.5 text-[12.5px] italic text-ink">
          “{scrub(prose)}”
        </p>
      )}
      {details.length > 0 && (
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[12px]">
          {details.map(({ label, value }) => (
            <div key={label} className="contents">
              <dt className="text-grey">{label}</dt>
              <dd className="text-navy">{scrub(String(value))}</dd>
            </div>
          ))}
        </dl>
      )}
      {prose === null && details.length === 0 && (
        <p className="mt-1.5 text-[12px] text-grey">The run continued as suggested.</p>
      )}
    </Card>
  );
}
