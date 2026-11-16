import { scrub } from "../../lib/scrub";
import { BRAND_MARK_SIZE } from "../../ui/brand/foldMark";
import { FoldMarkAnimated } from "../../ui/brand/FoldMarkAnimated";
import { cn } from "../../ui/brand/cn";
import { useArrives } from "../../ui/motion/arrivals";

/** The grey action line under an agent's reply while it works (task 058,
 *  N9; annex scene 10): what it is doing, with the Policy Atlas fold mark
 *  turning (owner, 2026-11-05: the mark, not the yellow dot, when the agent
 *  is working). The Task Agent and the chats share it (owner, round 14).
 *  After a dropped connection the mark holds still while the transcript is
 *  re-read. With no words yet the mark stands alone; a screen reader hears
 *  `quietLabel`.
 *
 *  Args:
 *    label: What the agent is doing, in the server's words, or null.
 *    live: True while the work is arriving (the mark turns).
 *    arrivalId: The line's arrival id (it rises when it arrives).
 *    quietLabel: What a screen reader hears when there are no words. */
export function ActionLine({
  label,
  live,
  arrivalId,
  quietLabel = "Working",
}: {
  label: string | null;
  live: boolean;
  arrivalId: string;
  quietLabel?: string;
}) {
  const arrives = useArrives(arrivalId);
  return (
    <p role="status" className={cn("mr-8 flex items-center gap-2 text-body text-grey", arrives && "anim-rise")}>
      <span className="inline-flex size-[17px] shrink-0 items-center justify-center" aria-hidden="true">
        <FoldMarkAnimated size={BRAND_MARK_SIZE} onDark={false} reducedMotion={live ? undefined : true} />
      </span>
      {label !== null ? scrub(label) : <span className="sr-only">{quietLabel}</span>}
    </p>
  );
}
