/**
 * Structural minimums, not the generated contract types.
 *
 * The view widens the artefact shape as it flows through (tuple year ranges
 * become arrays, and so on), so binding these helpers to `ArtefactOut` buys
 * nothing and costs a cast at every call site. They need a title, a nav
 * label and some citations — that is all they ask for.
 */

/** Typography shared across the report body (034 presentation). */
export const REPORT_PART_HEADING_CLASS =
  "text-[28px] font-extrabold uppercase tracking-[0.06em] leading-[1.2] text-navy";
export const REPORT_SECTION_HEADING_CLASS = "text-heading font-bold text-navy";
export const REPORT_BODY_CLASS = "text-lead text-ink";

/** Contents-sidebar anchors for report part headings. */
export const EXECUTIVE_SUMMARY_ANCHOR = "executive-summary";
export const FULL_REPORT_ANCHOR = "full-report";
type CitationLike = {
  source_id?: string | null;
  source_title?: string;
  appraisal_label?: string | null;
  evidence_type?: string | null;
};

type SectionLike = {
  title: string;
  nav_label?: string | null;
  blocks?: { claims?: { citations?: CitationLike[] }[] }[];
  cards?: { claims?: { citations?: CitationLike[] }[] }[];
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
  /** Author names, when the data carries them. */
  authors?: string[] | null;
  /** A short contextual note to render under the title. */
  note?: string | null;
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
    const claimSources: Array<{ claims?: { citations?: CitationLike[] }[] | null }> = [
      ...(section.blocks ?? []),
      ...(section.cards ?? []),
    ];
    for (const block of claimSources) {
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
              title: citation.source_title ?? "",
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

/**
 * Split a key-findings bullet on the first `: ` (task 034 S3).
 *
 * Display-only: stored prose is unchanged. No colon, or a colon with no
 * following space, returns null so the renderer leaves the line unbolded.
 */
export function splitLeadColon(text: string): { lead: string; rest: string } | null {
  const index = text.indexOf(": ");
  if (index <= 0) return null;
  return { lead: text.slice(0, index), rest: text.slice(index + 2) };
}

/**
 * Deterministic intro for the full-report part when synthesis did not produce one.
 */
export function fullReportIntro(
  sectionCount: number,
  generatedIntro?: string | null,
): string | null {
  if (sectionCount <= 0) return null;
  if (generatedIntro != null && generatedIntro.trim() !== "") return generatedIntro.trim();
  return null;
}

/** @deprecated Use {@link fullReportIntro} with a generated intro when available. */
export function reportRoadmap(_titles: string[]): string | null {
  return fullReportIntro(_titles.length);
}

/** Why case-study cards appear (matches the case-studies synthesis pass). */
export const CASE_STUDIES_INTRO = "Relevant examples from the cited evidence.";

/** Why these sources rank as most relevant (matches {@link mostRelevantSources}). */
export const MOST_RELEVANT_SOURCES_INTRO = "Sources cited most often in this report.";

type CardEvidenceInput = {
  strength?: string | null;
  design?: string | null;
  since_year?: number | null;
  claims?: Array<{ citations?: CitationLike[] }>;
};

/**
 * Strength, design and year for a case-study card.
 *
 * Rollup metadata is filled at synthesis from finding-level appraisal; when
 * that lookup misses, fall back to the card claims' citation rows.
 */
export function cardEvidenceMeta(card: CardEvidenceInput): {
  strength: string | null;
  design: string | null;
  sinceYear: number | null;
} {
  let strength = card.strength ?? null;
  let design = card.design ?? null;
  for (const claim of card.claims ?? []) {
    for (const citation of claim.citations ?? []) {
      if (strength == null && citation.appraisal_label != null && citation.appraisal_label !== "") {
        strength = citation.appraisal_label;
      }
      if (design == null && citation.evidence_type != null && citation.evidence_type !== "") {
        design = citation.evidence_type;
      }
    }
  }
  const sinceYear = card.since_year ?? null;
  return { strength, design, sinceYear };
}

/** Chip labels for a case-study card's evidence row (strength · design · since). */
export function cardEvidenceChipLabels(card: CardEvidenceInput): string[] {
  const { strength, design, sinceYear } = cardEvidenceMeta(card);
  return [
    strength,
    design,
    sinceYear != null ? `Since ${sinceYear}` : null,
  ].filter((part): part is string => part != null && part !== "");
}

function markdownKeyFindingsLine(line: string): string {
  const stripped = line.replace(/^\s*- /, "");
  const split = splitLeadColon(stripped);
  if (split === null) return `- ${stripped}`;
  return `- **${split.lead}:** ${split.rest}`;
}

function markdownKeyFindingsProse(prose: string): string {
  const lines = prose.split("\n").filter((line) => line.trim() !== "");
  const isBulleted = lines.length > 0 && lines.every((line) => line.trimStart().startsWith("- "));
  if (!isBulleted) return prose;
  return lines.map(markdownKeyFindingsLine).join("\n");
}

function markdownMostRelevantSources(sources: TopSource[]): string[] {
  if (sources.length === 0) return [];
  const lines: string[] = ["### Most relevant sources", "", MOST_RELEVANT_SOURCES_INTRO, ""];
  for (const source of sources) {
    const facts = [
      source.citationCount === 1 ? "cited by 1 claim" : `cited by ${source.citationCount} claims`,
      source.appraisalLabel,
      source.evidenceType,
    ].filter((part): part is string => part != null && part !== "");
    lines.push(`- **${source.title}** — ${facts.join(" · ")}.`);
    if (source.note != null && source.note !== "") lines.push(`  ${source.note}`);
  }
  lines.push("");
  return lines;
}

type MarkdownClaim = {
  claim_id?: string;
  claim_type?: string;
  span?: number[] | null;
  citations?: Array<{
    n?: number;
    source_id?: string | null;
    source_title?: string;
    appraisal_label?: string | null;
    evidence_type?: string | null;
  }>;
};

type MarkdownCard = {
  title: string;
  prose: string;
  claims?: MarkdownClaim[] | null;
  result_claim_id?: string | null;
  strength?: string | null;
  design?: string | null;
  since_year?: number | null;
};

type MarkdownSection = {
  title: string;
  role: "key_findings" | "case_studies" | "standard" | "conclusions";
  blocks?: Array<{ prose: string; claims?: MarkdownClaim[] | null }> | null;
  cards?: MarkdownCard[] | null;
};

function markdownCaseStudyCardProse(card: MarkdownCard): string {
  const claims = card.claims ?? [];
  const marked = proseWithCitationMarkers(card.prose, claims);
  const resultClaim = claims.find(
    (claim) => claim.claim_id != null && claim.claim_id === card.result_claim_id,
  );
  if (resultClaim?.span != null && resultClaim.span.length === 2) {
    const [start, end] = resultClaim.span;
    const resultText = Array.from(card.prose).slice(start, end).join("");
    if (resultText !== "") {
      const idx = marked.indexOf(resultText);
      if (idx >= 0) {
        return `${marked.slice(0, idx)}**${resultText}**${marked.slice(idx + resultText.length)}`;
      }
    }
  }
  return marked;
}

function mergeMostRelevantNotes(
  sources: TopSource[],
  notes?: Array<{ source_id: string; note: string }> | null,
): TopSource[] {
  if (notes == null || notes.length === 0) return sources;
  const notesBySourceId = new Map<string, string>();
  for (const entry of notes) {
    if (entry.source_id && entry.note) notesBySourceId.set(entry.source_id, entry.note);
  }
  return sources.map((source) => ({
    ...source,
    note: notesBySourceId.get(source.sourceId) ?? source.note ?? null,
  }));
}

type MarkdownArtefact = {
  title: string;
  summary?: string | null;
  summary_status?: "pending" | "verified" | "failed" | null;
  sections?: MarkdownSection[];
  references?: Array<{ n: number; title: string; year?: number | null; venue?: string | null }>;
  most_relevant_notes?: Array<{ source_id: string; note: string }> | null;
  full_report_intro?: string | null;
};

function citationMarker(claim: MarkdownClaim): string {
  const numbers = [
    ...new Set(
      (claim.citations ?? [])
        .map((citation) => citation.n)
        .filter((n): n is number => typeof n === "number"),
    ),
  ];
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
  const keyFindings = sections.filter((s) => s.role === "key_findings");
  const caseStudies = sections.filter((s) => s.role === "case_studies");
  const middle = sections.filter((s) => s.role === "standard");
  const conclusions = sections.filter((s) => s.role === "conclusions");
  return [...keyFindings, ...caseStudies, ...middle, ...conclusions];
}

/**
 * The report as a markdown file: title, executive summary (In brief + KF +
 * case studies + MRS), full report (roadmap + body sections + references).
 * Unverified summaries are omitted (same honesty as the on-screen callout).
 */
export function artefactMarkdown(artefact: MarkdownArtefact): string {
  const lines: string[] = [`# ${artefact.title}`, ""];
  const ordered = sectionsInReportOrder(artefact.sections ?? []);
  const execSections = ordered.filter(
    (s) => s.role === "key_findings" || s.role === "case_studies",
  );
  const fullReportSections = ordered.filter(
    (s) => s.role === "standard" || s.role === "conclusions",
  );

  lines.push("## Executive summary", "");
  for (const section of execSections) {
    lines.push(`### ${section.title}`, "");
    if (section.role === "case_studies") {
      lines.push(CASE_STUDIES_INTRO, "");
    }
    if (section.role === "case_studies" && (section.cards ?? []).length > 0) {
      for (const card of section.cards ?? []) {
        lines.push(`**${card.title}**`, "");
        if (card.prose) {
          lines.push(markdownCaseStudyCardProse(card), "");
        }
        const facts = cardEvidenceChipLabels(card);
        if (facts.length > 0) lines.push(`_${facts.join(" · ")}_`, "");
      }
    } else {
      for (const block of section.blocks ?? []) {
        const prose = proseWithCitationMarkers(block.prose, block.claims ?? []).trim();
        if (prose !== "") lines.push(markdownKeyFindingsProse(prose), "");
      }
    }
  }
  lines.push(
    ...markdownMostRelevantSources(
      mergeMostRelevantNotes(
        mostRelevantSources(artefact.sections),
        artefact.most_relevant_notes,
      ),
    ),
  );

  if (fullReportSections.length > 0) {
    lines.push("## Full report", "");
    const intro = fullReportIntro(fullReportSections.length, artefact.full_report_intro);
    if (intro !== null) lines.push(intro, "");
  }
  for (const section of fullReportSections) {
    lines.push(`### ${section.title}`, "");
    for (const block of section.blocks ?? []) {
      const prose = proseWithCitationMarkers(block.prose, block.claims ?? []).trim();
      if (prose !== "") lines.push(prose, "");
    }
  }
  const references = [...(artefact.references ?? [])].sort((left, right) => left.n - right.n);
  if (references.length > 0) {
    lines.push("### References", "");
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
