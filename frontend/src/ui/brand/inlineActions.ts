/*
 * The three inline-action styles (task 058 consistency pass; DESIGN.md
 * § Buttons, Inline actions). An action that reads as words, not as a
 * button, takes one of these and nothing else. Each sets no size, so it
 * takes the size of the line it sits in (Meta in a card, Body in prose)
 * unless the call site names one. A standalone Retry is never one of these:
 * it is `Button` secondary small.
 */

/** Link: Electric Blue Semibold, underlined on hover at a 3 px offset. The
 *  way to another view or another part of this one ("Sources →", "Read it →",
 *  "Expand all", "Ask about this analysis"). */
export const LINK_CLASS =
  "cursor-pointer font-semibold text-blue no-underline underline-offset-[3px] hover:underline " +
  "disabled:cursor-default disabled:text-grey disabled:no-underline";

/** Quiet control: Grey Semibold over a Line 2 underline that turns Navy on
 *  hover. A low-stakes toggle on what is already shown ("See the plan",
 *  "Show steps", "Change"). */
export const QUIET_CONTROL_CLASS =
  "cursor-pointer font-semibold text-grey underline decoration-line-2 underline-offset-[3px] " +
  "transition-colors duration-150 hover:text-navy hover:decoration-navy " +
  "disabled:cursor-default disabled:no-underline disabled:hover:text-grey";

/** Prose link: Navy, always underlined, Electric Blue on hover. A link
 *  inside running text (legal pages, a project named in a sentence). */
export const PROSE_LINK_CLASS =
  "text-navy underline underline-offset-[3px] transition-colors duration-150 hover:text-blue";
