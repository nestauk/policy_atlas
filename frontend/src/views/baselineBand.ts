/**
 * What marks an artefact as an options-scoping baseline (task 044,
 * deliverable 9). The Result's band under the title came off on the owner's
 * ruling of 2026-09-18; the plan document carries the walk's state.
 */

/** The roll-up's template key for a baseline (`counts.template`, written by
 *  synthesise in baseline mode). */
export const BASELINE_TEMPLATE = "baseline";

interface ArtefactTemplateFields {
  template?: string | null;
  depth_label?: string | null;
}

/** Whether this artefact is an options-scoping baseline. Reads the roll-up's
 *  own word — never inferred from the section titles or the task's kind. */
export function isBaselineArtefact(artefact: ArtefactTemplateFields | null | undefined): boolean {
  return artefact?.template === BASELINE_TEMPLATE;
}
