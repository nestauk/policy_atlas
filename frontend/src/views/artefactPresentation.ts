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

type MarkdownClaim = {
  claim_type?: string;
  span?: number[] | null;
  citations?: Array<{ n: number }>;
};

type MarkdownSection = {
  title: string;
  role: "key_findings" | "standard" | "conclusions";
  blocks?: Array<{ prose: string; claims?: MarkdownClaim[] | null }> | null;
};

type MarkdownArtefact = {
  title: string;
  summary?: string | null;
  summary_status?: "pending" | "verified" | "failed" | null;
  sections?: MarkdownSection[];
  references?: Array<{ n: number; title: string; year?: number | null; venue?: string | null }>;
};

function citationMarker(claim: MarkdownClaim): string {
  const numbers = [...new Set((claim.citations ?? []).map((citation) => citation.n))];
  return numbers.length > 0 ? `[${numbers.join(",")}]` : "";
}

/**
 * Put `[n]` back after each citation span.
 *
 * Report prose does not store those markers — the on-screen view paints them
 * from claim citations. A markdown file without them has no way to reach the
 * numbered list at the end. Span offsets are Python code points, same as
 * `spanSegments`.
 */
function proseWithCitationMarkers(prose: string, claims: MarkdownClaim[]): string {
  const chars = Array.from(prose);
  const spanned = claims
    .filter(
      (claim): claim is MarkdownClaim & { span: [number, number] } =>
        claim.span != null &&
        claim.span.length === 2 &&
        claim.span[0] >= 0 &&
        claim.span[1] <= chars.length &&
        claim.span[0] < claim.span[1],
    )
    .sort((left, right) => left.span[0] - right.span[0]);
  const parts: string[] = [];
  let cursor = 0;
  for (const claim of spanned) {
    if (claim.span[0] < cursor) continue;
    if (claim.span[0] > cursor) {
      parts.push(chars.slice(cursor, claim.span[0]).join(""));
    }
    parts.push(chars.slice(claim.span[0], claim.span[1]).join(""));
    if (claim.claim_type === "citation") {
      const marker = citationMarker(claim);
      if (marker !== "") parts.push(marker);
    }
    cursor = claim.span[1];
  }
  if (cursor < chars.length) parts.push(chars.slice(cursor).join(""));
  return parts.join("");
}

function sectionsInReportOrder(sections: MarkdownSection[]): MarkdownSection[] {
  const keyFindings = sections.filter((section) => section.role === "key_findings");
  const middle = sections.filter(
    (section) => section.role !== "key_findings" && section.role !== "conclusions",
  );
  const conclusions = sections.filter((section) => section.role === "conclusions");
  return [...keyFindings, ...middle, ...conclusions];
}

/**
 * The report as a markdown file: title, verified summary, section prose,
 * numbered references. Unverified summaries are omitted (same honesty as
 * the on-screen callout).
 */
export function artefactMarkdown(artefact: MarkdownArtefact): string {
  const lines: string[] = [`# ${artefact.title}`, ""];
  if (artefact.summary_status === "verified" && artefact.summary != null && artefact.summary !== "") {
    lines.push(artefact.summary, "");
  }
  for (const section of sectionsInReportOrder(artefact.sections ?? [])) {
    lines.push(`## ${section.title}`, "");
    for (const block of section.blocks ?? []) {
      const prose = proseWithCitationMarkers(block.prose, block.claims ?? []).trim();
      if (prose !== "") lines.push(prose, "");
    }
  }
  const references = [...(artefact.references ?? [])].sort((left, right) => left.n - right.n);
  if (references.length > 0) {
    lines.push("## References", "");
    for (const reference of references) {
      const extra = [
        reference.year != null ? String(reference.year) : null,
        reference.venue ?? null,
      ].filter((part): part is string => part !== null);
      lines.push(
        extra.length > 0
          ? `${reference.n}. ${reference.title} (${extra.join(", ")})`
          : `${reference.n}. ${reference.title}`,
      );
    }
    lines.push("");
  }
  return lines.join("\n");
}

/** A filesystem-safe stem from the report title, with a fallback. */
export function downloadFilename(title: string, extension: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return `${slug || "evidence-base"}.${extension}`;
}

/** Trigger a client-side file download of UTF-8 text. */
export function triggerTextDownload(filename: string, body: string, mime: string): void {
  const blob = new Blob([body], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
