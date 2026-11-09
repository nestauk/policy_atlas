/**
 * The Label style (DESIGN.md § Typography, Label): Meta size, bold,
 * uppercase, tracked on the `--tracking-label` token, grey. One class for
 * every small uppercase label on the plan and check-in cards, so the
 * tracking cannot drift between them (task 058, N18).
 */
export const LABEL_CLASS = "text-meta font-bold uppercase tracking-label text-grey";

/** The pane heading and table header form of the Label style: Extrabold
 *  (DESIGN.md § Cards / Containers, Pane heading). */
export const PANE_LABEL_CLASS = "text-meta font-extrabold uppercase tracking-label text-grey";

/** The Label style at Caption size: the conversation list's and the settled
 *  scope card's group labels, the task kind beside a title. */
export const CAPTION_LABEL_CLASS = "text-caption font-bold uppercase tracking-label text-grey";
