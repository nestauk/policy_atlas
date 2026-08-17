/**
 * Structural minimums, not the generated contract types.
 *
 * The view widens the artefact shape as it flows through (tuple year ranges
 * become arrays, and so on), so binding these helpers to `ArtefactOut` buys
 * nothing and costs a cast at every call site. They need a title, a nav
 * label and some citations — that is all they ask for.
 */
type CitationLike = {
  source_id?: string | null;
  source_title: string;
  appraisal_label?: string | null;
  evidence_type?: string | null;
};

type SectionLike = {
  title: string;
  nav_label?: string | null;
  blocks?: { claims?: { citations?: CitationLike[] }[] }[];
};

/** One source the report leans on, with only facts about it. */
export type TopSource = {
  sourceId: string;
  title: string;
  /** How many report claims cite it — the ranking key. */
  citationCount: number;
  /** The appraisal label the assessment gave it, when it has one. */
  appraisalLabel: string | null;
  /** The classified evidence type, when it has one. */
  evidenceType: string | null;
  /** Titles of the sections that cite it, in page order. */
  citedInSections: string[];
};

/**
 * Appraisal labels, strongest first, for the tie-break only.
 *
 * A label outside this list sorts last rather than throwing — an
 * unclassified source is a real state, and the ranking is a convenience, not
 * a place to fail.
 */
const APPRAISAL_ORDER = ["high", "moderate", "low", "very_low"] as const;

function appraisalRank(label: string | null): number {
  if (label === null) return APPRAISAL_ORDER.length;
  const index = APPRAISAL_ORDER.indexOf(label.toLowerCase() as (typeof APPRAISAL_ORDER)[number]);
  return index === -1 ? APPRAISAL_ORDER.length : index;
}

/**
 * The sources the report cites most, at most three.
 *
 * Ranked by how many claims cite each source, ties broken by appraisal tier
 * and then title so the order is stable rather than incidental to object
 * insertion. Every field returned is something the data already asserts —
 * how often it is cited, its tier, its type, where it appears. Nothing here
 * says why a study matters; that is a judgement the system has not made and
 * must not imply.
 */
export function mostRelevantSources(
  sections: readonly SectionLike[] | undefined,
  limit = 3,
): TopSource[] {
  const bySource = new Map<string, TopSource>();
  for (const section of sections ?? []) {
    for (const block of section.blocks ?? []) {
      for (const claim of block.claims ?? []) {
        // One claim citing the same source twice counts once for that claim:
        // the ranking is "how many claims lean on this", not "how many
        // citation rows exist".
        const seenInClaim = new Set<string>();
        for (const citation of claim.citations ?? []) {
          const sourceId = citation.source_id;
          if (sourceId == null || seenInClaim.has(sourceId)) continue;
          seenInClaim.add(sourceId);

          const existing = bySource.get(sourceId);
          if (existing === undefined) {
            bySource.set(sourceId, {
              sourceId,
              title: citation.source_title,
              citationCount: 1,
              appraisalLabel: citation.appraisal_label ?? null,
              evidenceType: citation.evidence_type ?? null,
              citedInSections: [section.title],
            });
          } else {
            existing.citationCount += 1;
            existing.appraisalLabel ??= citation.appraisal_label ?? null;
            existing.evidenceType ??= citation.evidence_type ?? null;
            if (!existing.citedInSections.includes(section.title)) {
              existing.citedInSections.push(section.title);
            }
          }
        }
      }
    }
  }

  return [...bySource.values()]
    .sort(
      (left, right) =>
        right.citationCount - left.citationCount ||
        appraisalRank(left.appraisalLabel) - appraisalRank(right.appraisalLabel) ||
        left.title.localeCompare(right.title),
    )
    .slice(0, limit);
}

/**
 * The label for a section in the contents list.
 *
 * `nav_label` when the synthesis produced one. Artefacts made before that
 * field existed have none, which is a normal state, so the title is shortened
 * here rather than rejected — the clip is a display convenience, unlike the
 * proposal boundary's hard 28-character rule, which rejects.
 */
export function sectionNavLabel(section: SectionLike, max = 28): string {
  const label = section.nav_label;
  if (label != null && label.trim() !== "") return label;
  const title = section.title.trim();
  if (title.length <= max) return title;
  const clipped = title.slice(0, max);
  const lastSpace = clipped.lastIndexOf(" ");
  return `${(lastSpace > max / 2 ? clipped.slice(0, lastSpace) : clipped).trimEnd()}…`;
}
