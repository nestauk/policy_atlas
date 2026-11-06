import { evidenceTypeLabel, strengthRank } from "../ui/brand/evidence";

/**
 * Structural minimums, not the generated contract types.
 *
 * The view widens the artefact shape as it flows through (tuple year ranges
 * become arrays, and so on), so binding these helpers to `ArtefactOut` buys
 * nothing and costs a cast at every call site. They need a title, a nav
 * label and some citations — that is all they ask for.
 */

/** Typography shared across the report body (034 presentation). The part
 *  heading ("Executive summary", "Full report") is Heading, uppercase,
 *  Extrabold and tracked (lead ruling, task 058 consistency pass); a section
 *  heading is Heading, Lead below md. Both are on the named scale. */
export const REPORT_PART_HEADING_CLASS =
  "text-heading font-extrabold uppercase tracking-label text-navy";
export const REPORT_SECTION_HEADING_CLASS = "text-heading font-bold text-navy max-md:text-lead";
export const REPORT_BODY_CLASS = "text-lead text-ink max-md:text-body";

/** Contents-sidebar anchors for report part headings. */
export const EXECUTIVE_SUMMARY_ANCHOR = "executive-summary";
export const FULL_REPORT_ANCHOR = "full-report";
type CitationLike = {
  source_id?: string | null;
  source_title?: string;
  appraisal_label?: string | null;
  evidence_type?: string | null;
};

type ClaimSourceLike = {
  claim_id?: string;
  citations?: CitationLike[] | null;
};

type ClaimBearerLike = { claims?: ClaimSourceLike[] | null };

type SectionLike = {
  title: string;
  nav_label?: string | null;
  blocks?: ClaimBearerLike[] | null;
  cards?: ClaimBearerLike[] | null;
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
  // Case-study cards carry re-projections of their section block's claims
  // (same claim_id), so a claim seen under both must count once.
  const seenClaimIds = new Set<string>();
  for (const section of sections ?? []) {
    const claimSources: ClaimBearerLike[] = [
      ...(section.blocks ?? []),
      ...(section.cards ?? []),
    ];
    for (const block of claimSources) {
      for (const claim of block.claims ?? []) {
        if (claim.claim_id != null) {
          if (seenClaimIds.has(claim.claim_id)) continue;
          seenClaimIds.add(claim.claim_id);
        }
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
        strengthRank(left.appraisalLabel) - strengthRank(right.appraisalLabel) ||
        left.title.localeCompare(right.title),
    )
    .slice(0, limit);
}

/** One author (or corporate author) and their institutions (042 wire shape). */
export type AuthorshipLike = { name: string; institutions?: string[] | null };

/** Words that mark a name as an organisation's, not a person's. */
const ORGANISATION_WORDS = new Set([
  "agency",
  "association",
  "authority",
  "bank",
  "board",
  "centre",
  "center",
  "commission",
  "committee",
  "council",
  "department",
  "foundation",
  "government",
  "group",
  "institute",
  "ministry",
  "network",
  "office",
  "organisation",
  "organization",
  "partnership",
  "service",
  "society",
  "trust",
  "university",
]);

/** Lower-case particles that belong to a surname ("van der Berg"). */
const SURNAME_PARTICLES = new Set(["van", "von", "der", "den", "de", "del", "della", "da", "di", "du", "la", "le", "ter", "ten"]);

/**
 * One author as the reference list names them (round 10, C5): the surname,
 * then the initials of the given names, "Sampleton A" for "Alex Sampleton"
 * and "Sampleton AJ" for "Sampleton, Alex J.". An organisation, a single
 * name or a name the rule cannot read as a person's is kept as written.
 *
 * Args:
 *   name: The author's name as the source record gives it.
 *
 * Returns:
 *   The short form, or the name unchanged.
 */
export function referenceAuthorName(name: string): string {
  const trimmed = name.trim().replace(/\s+/g, " ");
  const initials = (given: string) =>
    given
      .split(/[\s-]+/)
      .map((part) => part.replace(/[^\p{L}]/gu, ""))
      .filter((part) => part !== "")
      .map((part) => part.charAt(0).toUpperCase())
      .join("");
  const words = trimmed.split(" ");
  const organisational =
    /[\d&()]/.test(trimmed) ||
    words.some((word) => ORGANISATION_WORDS.has(word.toLowerCase().replace(/[^\p{L}]/gu, ""))) ||
    words.some((word) => /^\p{Lu}{2,}$/u.test(word)) ||
    words.some((word, at) => at > 0 && ["for", "of", "and", "the", "on", "in"].includes(word));
  if (organisational) return trimmed;
  const comma = trimmed.split(", ");
  if (comma.length === 2 && comma[0] !== "" && comma[1] !== "") {
    const given = initials(comma[1]);
    return given === "" ? trimmed : `${comma[0]} ${given}`;
  }
  if (words.length < 2 || words.length > 4) return trimmed;
  let surnameAt = words.length - 1;
  while (surnameAt > 1 && SURNAME_PARTICLES.has(words[surnameAt - 1])) surnameAt -= 1;
  const given = initials(words.slice(0, surnameAt).join(" "));
  return given === "" ? trimmed : `${words.slice(surnameAt).join(" ")} ${given}`;
}

/**
 * The reference list's authors (round 10, C5): up to three in the short form
 * ("Sampleton A, Mockford C"), a longer list the first three and "et al.";
 * null with none, so the reference starts at its title.
 */
export function referenceAuthorsShort(
  authorships: readonly AuthorshipLike[] | null | undefined,
): string | null {
  const names = (authorships ?? []).map((a) => a.name.trim()).filter((name) => name !== "").map(referenceAuthorName);
  if (names.length === 0) return null;
  if (names.length > 3) return `${names.slice(0, 3).join(", ")} et al.`;
  return names.join(", ");
}

/** A source's web address as the reference list shows it on screen: without
 *  the scheme ("doi.org/10.1000/x"); print shows the full address. */
export function displayUrl(url: string): string {
  return url.trim().replace(/^https?:\/\//i, "").replace(/\/$/, "");
}

/** `text` ending in one full stop: none added after a closing ".", "?" or "!". */
export function withFullStop(text: string): string {
  const trimmed = text.trim();
  return /[.?!]$/.test(trimmed) ? trimmed : `${trimmed}.`;
}

/** A reference as the report lists it (round 10, C5). */
export type ReferenceLike = {
  title: string;
  year?: number | null;
  venue?: string | null;
  url?: string | null;
  authorships?: readonly AuthorshipLike[] | null;
};

/**
 * One reference's parts in the citation form "Sampleton A, Mockford C
 * (2022). Title. Venue. https://…" (round 10, C5), shared by the page and the
 * Markdown download: `lead` before the title (authors and year, or null with
 * no authors), `afterTitle` straight after it (" (2022)." when there are no
 * authors to carry the year, "." otherwise, nothing after a title that ends
 * in its own stop), the venue with its full stop, and the web address when it
 * is one.
 */
export function referenceParts(reference: ReferenceLike): {
  lead: string | null;
  title: string;
  afterTitle: string;
  venue: string | null;
  url: string | null;
} {
  const authors = referenceAuthorsShort(reference.authorships);
  const year = reference.year ?? null;
  const title = reference.title.trim();
  const lead = authors === null ? null : year !== null ? `${authors} (${year}). ` : `${withFullStop(authors)} `;
  const afterTitle = authors === null && year !== null ? ` (${year}).` : /[.?!]$/.test(title) ? "" : ".";
  const venue = reference.venue != null && reference.venue.trim() !== "" ? withFullStop(reference.venue) : null;
  const url = reference.url != null && /^https?:\/\//i.test(reference.url.trim()) ? reference.url.trim() : null;
  return { lead, title, afterTitle, venue, url };
}

/** A reference in the citation form as one line of text, the full address
 *  at its end (the Markdown download; print shows the same). */
export function referenceCitation(reference: ReferenceLike): string {
  const { lead, title, afterTitle, venue, url } = referenceParts(reference);
  return [`${lead ?? ""}${title}${afterTitle}`, venue, url].filter((part): part is string => part !== null).join(" ");
}

export type NumberedAuthorships = {
  /** Authors in wire order, each with the marker numbers of its institutions. */
  authors: Array<{ name: string; markers: number[] }>;
  /** Institutions deduped, ordered by first appearance; marker n = index n-1. */
  institutions: string[];
};

/**
 * Superscript affiliation numbering (042 D5): institutions dedupe and number
 * by first appearance; each author carries its institutions' marker numbers.
 * An author without institutions carries no markers (a corporate author is
 * the one-name/no-institution case).
 */
export function numberedAuthorships(
  authorships: readonly AuthorshipLike[] | null | undefined,
): NumberedAuthorships {
  const institutions: string[] = [];
  const markerByInstitution = new Map<string, number>();
  const authors = (authorships ?? [])
    .filter((a) => a.name !== "")
    .map((a) => ({
      name: a.name,
      // Set-dedupe within one author: duplicate affiliation records slimming
      // to the same display name must not render as a repeated marker (¹,¹).
      markers: [...new Set((a.institutions ?? []).filter((institution) => institution !== ""))]
        .map((institution) => {
          const existing = markerByInstitution.get(institution);
          if (existing !== undefined) return existing;
          institutions.push(institution);
          markerByInstitution.set(institution, institutions.length);
          return institutions.length;
        }),
    }));
  return { authors, institutions };
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
 * The full-report roadmap line: the synthesised intro when one was produced,
 * otherwise nothing (absence is a normal state, never a fabricated line).
 */
export function fullReportIntro(
  sectionCount: number,
  generatedIntro?: string | null,
): string | null {
  if (sectionCount <= 0) return null;
  if (generatedIntro != null && generatedIntro.trim() !== "") return generatedIntro.trim();
  return null;
}

/** Why case-study cards appear (matches the case-studies synthesis pass). */
export const CASE_STUDIES_INTRO = "Relevant examples from the cited evidence.";

/** Why these sources rank as most relevant (matches {@link mostRelevantSources}). */
export const MOST_RELEVANT_SOURCES_INTRO = "Sources cited most often in this report.";

type CardEvidenceInput = {
  strength?: string | null;
  design?: string | null;
  since_year?: number | null;
  claims?: ClaimSourceLike[] | null;
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

/**
 * The cited source a case-study card's evidence type came from: the first
 * citation of that type, in the order the card's own fields were filled
 * (round 12). Its dossier holds the classifier's reasoning for the type,
 * which the artefact does not carry. `null` when no citation names it.
 */
export function cardEvidenceSourceId(card: CardEvidenceInput, design: string | null): string | null {
  if (design === null) return null;
  for (const claim of card.claims ?? []) {
    for (const citation of claim.citations ?? []) {
      if (citation.evidence_type === design && citation.source_id != null && citation.source_id !== "") {
        return citation.source_id;
      }
    }
  }
  return null;
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
      source.evidenceType === null ? null : evidenceTypeLabel(source.evidenceType),
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

/** Attach grounded one-liner notes to their ranked sources (034 S5). */
export function mergeMostRelevantNotes(
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
  references?: Array<ReferenceLike & { n: number }>;
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
 * The report as a markdown file, in the page's order (rounds 10 and 11): the
 * question as the title (the generated title when there is none), the
 * executive summary (key findings, case studies, the most relevant sources),
 * the full report (its opening paragraph and body sections), then the
 * references in the citation form. Unverified summaries are omitted (same
 * honesty as the on-screen callout).
 *
 * Args:
 *   artefact: The committed report.
 *   question: The task's question, the page's title; the file's name stays
 *     the generated title's.
 *
 * Returns:
 *   The Markdown text.
 */
export function artefactMarkdown(artefact: MarkdownArtefact, question?: string | null): string {
  const heading = question != null && question.trim() !== "" ? question.trim() : artefact.title;
  const lines: string[] = [`# ${heading}`, ""];
  const ordered = sectionsInReportOrder(artefact.sections ?? []);
  const execSections = ordered.filter(
    (s) => s.role === "key_findings" || s.role === "case_studies",
  );
  const fullReportSections = ordered.filter(
    (s) => s.role === "standard" || s.role === "conclusions",
  );

  lines.push("## Executive summary", "");
  for (const section of execSections) {
    if (section.role === "case_studies") {
      // Parity with the page: a case-studies section with no cards renders
      // nothing (absence is normal, never an empty heading).
      const cards = section.cards ?? [];
      if (cards.length === 0) continue;
      lines.push(`### ${section.title}`, "", CASE_STUDIES_INTRO, "");
      for (const card of cards) {
        lines.push(`**${card.title}**`, "");
        if (card.prose) {
          lines.push(markdownCaseStudyCardProse(card), "");
        }
        const { strength, design, sinceYear } = cardEvidenceMeta(card);
        const facts = [design === null ? null : evidenceTypeLabel(design), strength, sinceYear != null ? `Since ${sinceYear}` : null].filter(
          (part): part is string => part != null && part !== "",
        );
        if (facts.length > 0) lines.push(`_${facts.join(" · ")}_`, "");
      }
    } else {
      lines.push(`### ${section.title}`, "");
      for (const block of section.blocks ?? []) {
        const prose = proseWithCitationMarkers(block.prose, block.claims ?? []).trim();
        if (prose !== "") lines.push(markdownKeyFindingsProse(prose), "");
      }
    }
  }
  // The executive summary's last part, as on the page (owner, round 11).
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
      lines.push(`${reference.n}. ${referenceCitation(reference)}`);
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
  return `${slug || "report"}.${extension}`;
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

/** The longest source name the "Drawing on" line shows in full. */
const LIVE_SOURCE_NAME_MAX = 40;

/**
 * A source's name as the live "Drawing on" line shows it (task 058, owner
 * 2026-11-05). The server sends the short form ("Smith 2023") when it has
 * one, else the title; a long title is cut at a word near 40 characters and
 * ends with an ellipsis.
 */
export function liveSourceName(title: string): string {
  const name = title.trim().replace(/\s+/g, " ");
  if (name.length <= LIVE_SOURCE_NAME_MAX) return name;
  const cut = name.slice(0, LIVE_SOURCE_NAME_MAX);
  const space = cut.lastIndexOf(" ");
  return `${(space > LIVE_SOURCE_NAME_MAX / 2 ? cut.slice(0, space) : cut).replace(/[\s,.;:–—-]+$/, "")}…`;
}

/** How many sources the "Drawing on" line names before "and N more". */
const LIVE_SOURCES_NAMED = 3;

/**
 * The line under a section being written that says which sources the writer
 * has read: "Drawing on 4 sources · Smith 2023 · DfE 2022 · Nesta 2021 · and
 * 1 more". Null when it has read none.
 */
export function drawingOnLine(sources: readonly { title: string }[] | undefined): string | null {
  if (sources === undefined || sources.length === 0) return null;
  const count = sources.length === 1 ? "1 source" : `${sources.length} sources`;
  const named = sources.slice(0, LIVE_SOURCES_NAMED).map((source) => liveSourceName(source.title));
  const rest = sources.length - named.length;
  return [`Drawing on ${count}`, ...named, ...(rest > 0 ? [`and ${rest} more`] : [])].join(" · ");
}
