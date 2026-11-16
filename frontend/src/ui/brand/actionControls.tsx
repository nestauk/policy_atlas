import type { ReactElement } from "react";

import { Tooltip, TooltipProvider } from "../radix/Tooltip";
import { cn } from "./cn";
import { ExcludeIcon, UndoIcon } from "./icons";
import { QUIET_CONTROL_CLASS } from "./inlineActions";

/*
 * The quiet action control with a glyph before its words (round 13, owner),
 * shared by two capabilities: Options scoping's Exclude and Include again,
 * and the theory of change's Remove and Restore on a document (058
 * alignment, phase 7). Grey, never red.
 */

/** A quiet text control with a 12 px glyph before the words, in the
 *  control's colour. */
export const ACTION_CONTROL_CLASS = cn(
  QUIET_CONTROL_CLASS,
  "inline-flex items-center gap-1.5 text-meta disabled:cursor-not-allowed disabled:opacity-40",
);

/** The glyph before a control that leaves something out (a circle with a
 *  bar) or brings it back (an arrow turning back); a caller may draw it at
 *  another size. */
export function ActionGlyph({ include, size = 12 }: { include: boolean; size?: number }) {
  return include ? <UndoIcon size={size} className="shrink-0" /> : <ExcludeIcon size={size} className="shrink-0" />;
}

/** A control with a tooltip in the system's skin, or the control alone
 *  when there is no note. */
export function WithTooltip({ note, children }: { note?: string; children: ReactElement }) {
  if (note === undefined) return children;
  return (
    <TooltipProvider delayDuration={250}>
      <Tooltip content={<p className="text-meta">{note}</p>}>{children}</Tooltip>
    </TooltipProvider>
  );
}
