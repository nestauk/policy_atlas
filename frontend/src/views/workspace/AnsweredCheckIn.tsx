import { scrub } from "../../lib/scrub";
import type { ResolvedDecision, StageEntry } from "../../store";
import type { CheckInOut } from "../../store/types";
import { chosenLine } from "./checkInPresentation";

/**
 * An answered check-in collapses to one quiet line (task 058, N19; annex
 * scene 12): "You chose: <label> · <when>", built from the durable
 * `checkin.resolved` frame and the check-in's own option labels, so it
 * reads the same after a reload or on another device. Raw option ids and
 * raw params never render.
 */
export function AnsweredCheckIn({
  decision,
  checkIn,
  stages,
}: {
  decision: ResolvedDecision;
  checkIn?: CheckInOut;
  stages: StageEntry[];
}) {
  const line = chosenLine(decision, checkIn, stages);
  return (
    <p data-testid="answered-check-in" className="anim-rise mr-8 text-body text-grey">
      {line === null ? "The run continued as suggested." : scrub(line)}
    </p>
  );
}
