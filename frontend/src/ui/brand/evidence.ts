/**
 * The shared evidence vocabulary (task 058, round 12 consolidation; owner
 * 2026-11-06: one central place for strength tones and the like, so no
 * view re-implements them and drifts). Every surface that names an
 * evidence strength, a read depth, an evidence type or a judge's verdict
 * imports it from here: the Sources table and dossier, the report's chips
 * and citation sheet, chat's citation block, the Landscape charts and the
 * longlist. A view-level copy of any rule below is a defect (DESIGN.md).
 *
 * The 6 px tone square and the marks built from it live beside this file in
 * `EvidenceMarks.tsx`.
 */

// ---------------------------------------------------------------------------
// Evidence strength
// ---------------------------------------------------------------------------

/** The appraised strengths, strongest first: the backend's
 *  `appraise.SCORE_LABELS` plus "Unrated" (task 056: no score), in the
 *  sort's order. The Sources filter offers them in this order. */
export const STRENGTH_TIERS = ["Very strong", "Strong", "Moderate", "Limited", "Weak", "Unrated"] as const;

export type StrengthTier = (typeof STRENGTH_TIERS)[number];

/**
 * A strength's rank, strongest first (0 for Very strong); a label outside
 * the vocabulary, or none, ranks after every tier. Case does not matter.
 *
 * Args:
 *   tier: The appraised strength as the server sends it.
 *
 * Returns:
 *   Its index in `STRENGTH_TIERS`, or the list's length when unknown.
 */
export function strengthRank(tier: string | null | undefined): number {
  if (!tier) return STRENGTH_TIERS.length;
  const index = STRENGTH_TIERS.findIndex((known) => known.toLowerCase() === tier.toLowerCase());
  return index === -1 ? STRENGTH_TIERS.length : index;
}

/**
 * The tone of an appraised strength (round 11; round 12 gives every level a
 * colour): Very strong and Strong are strong, Moderate and Limited moderate,
 * Weak and Unrated weak, in the sort's order. A tier outside the vocabulary
 * has no tone, so no square.
 */
export type StrengthTone = "strong" | "moderate" | "weak";

const STRENGTH_TONES: Record<StrengthTier, StrengthTone> = {
  "Very strong": "strong",
  Strong: "strong",
  Moderate: "moderate",
  Limited: "moderate",
  Weak: "weak",
  Unrated: "weak",
};

/** The strength's tone, or `null` for a tier the vocabulary does not hold. */
export function strengthTone(tier: string | null | undefined): StrengthTone | null {
  return tier ? (STRENGTH_TONES[tier as StrengthTier] ?? null) : null;
}

/** The palette colour a tone square takes: the palette's own green, yellow
 *  and red (round 12; no new colours). */
export type ToneColour = "green" | "yellow" | "red";

const STRENGTH_COLOURS: Record<StrengthTone, ToneColour> = { strong: "green", moderate: "yellow", weak: "red" };

/** The colour of a strength's tone square. */
export function strengthColour(tone: StrengthTone): ToneColour {
  return STRENGTH_COLOURS[tone];
}

/** A tier's square colour in one step, or `null` outside the vocabulary. */
export function strengthTierColour(tier: string | null | undefined): ToneColour | null {
  const tone = strengthTone(tier);
  return tone === null ? null : strengthColour(tone);
}

/**
 * The 6 px tone square in Tailwind classes: the palette's fill, square, not
 * shrinking in a flex row. It always sits before its word, which carries the
 * meaning in text (the Word Beside the Colour Rule).
 *
 * Args:
 *   colour: The tone's palette colour.
 *
 * Returns:
 *   The square's classes.
 */
export function toneSquareClass(colour: ToneColour): string {
  const fill = colour === "green" ? "bg-green" : colour === "yellow" ? "bg-yellow" : "bg-red";
  return `inline-block size-1.5 shrink-0 ${fill}`;
}

/** The strength legend (round 12): each square colour beside the tiers it
 *  marks, in the sort's order, read from the tones above so it cannot
 *  drift from them ("Very strong, Strong"; "Moderate, Limited"; "Weak,
 *  Unrated"). */
export const STRENGTH_LEGEND: ReadonlyArray<{ colour: ToneColour; tiers: string }> = (
  ["green", "yellow", "red"] as const
).map((colour) => ({
  colour,
  tiers: STRENGTH_TIERS.filter((tier) => STRENGTH_COLOURS[STRENGTH_TONES[tier]] === colour).join(", "),
}));

/** The strength's hover when the source carries no evidence type to name. */
export const STRENGTH_FALLBACK_HINT =
  "The source's appraised evidence strength — five bands from Weak to Very strong, scored from its classified document type; Unrated when the type is not scored.";

/**
 * The strength's hover, one sentence for every surface (the table, the
 * dossier, the report's chips and the citation sheet): how it was appraised
 * from the document type, or why an Unrated source is not scored.
 *
 * Args:
 *   tier: The appraised strength.
 *   evidenceType: The classifier's evidence type, when the source has one.
 *
 * Returns:
 *   The sentence, the type in sentence case.
 */
export function strengthHint(tier: string | null | undefined, evidenceType: string | null | undefined): string {
  if (!tier || typeof evidenceType !== "string" || evidenceType.trim() === "") return STRENGTH_FALLBACK_HINT;
  const type = evidenceTypeLabel(evidenceType);
  return tier === "Unrated"
    ? `Unrated — the document type (${type}) is not scored; the source can be cited but counts below the evidence bar.`
    : `${tier} evidence strength — appraised from the document type: ${type}.`;
}

// ---------------------------------------------------------------------------
// Read depth (the Status column)
// ---------------------------------------------------------------------------

/** The read depth's words: what of the source the analysis had to read. */
export const FULL_TEXT = "Full text";
export const ABSTRACT_ONLY = "Abstract only";
export const TITLE_ONLY = "Title only";

export type ReadDepth = typeof FULL_TEXT | typeof ABSTRACT_ONLY | typeof TITLE_ONLY;

const DEPTH_COLOURS: Record<ReadDepth, ToneColour> = {
  [FULL_TEXT]: "green",
  [ABSTRACT_ONLY]: "yellow",
  [TITLE_ONLY]: "red",
};

/** The fields a read depth is read from (an evidence row or a dossier). */
export type DepthSource = {
  read_in_full: boolean;
  screen_status?: string | null;
  status: string;
  status_reason?: string | null;
  abstract?: string | null;
};

/**
 * Read depth (owner, 2026-08-05; round 12 gives each a tone): "Full text"
 * when the text was collected; "Abstract only" when the source carries an
 * abstract and no text; "Title only" when it carries neither. Not read past
 * screening gives `null` (the cell stays empty).
 *
 * Args:
 *   item: The source's read and screening state.
 *
 * Returns:
 *   The depth's word, or null.
 */
export function readDepthLabel(item: Pick<DepthSource, "read_in_full" | "screen_status" | "status" | "abstract">): ReadDepth | null {
  // "Full text", not "Read in full": the text is fetched and made
  // searchable, not read by a model at that step (owner, round 9).
  if (item.read_in_full) return FULL_TEXT;
  if (item.status === "unavailable" || item.screen_status === "relevant") {
    return item.abstract?.trim() ? ABSTRACT_ONLY : TITLE_ONLY;
  }
  return null;
}

/** The read depth's tone square (round 12): green full text, yellow
 *  abstract, red neither. */
export function readDepthColour(depth: ReadDepth): ToneColour {
  return DEPTH_COLOURS[depth];
}

/** Human sentences for the backend's fetch and screening reason codes, so
 *  raw codes never render. The fetch codes mirror `ingest_full_text`'s
 *  failure vocabulary. */
const HUMAN_REASON: Record<string, string> = {
  title_only: "Screened on the title only",
  title_abstract: "Screened on the title and abstract",
  fetch_failed: "The full text couldn't be fetched",
  parse_failed: "The document couldn't be parsed",
  no_url: "No full-text link was available",
  paywall: "The full text is behind a paywall",
  not_found: "The full-text link no longer works",
  too_large: "The document was too large to process",
  timeout: "The fetch timed out",
  corrupt: "The file was corrupt",
  no_text_layer: "The PDF had no extractable text",
  thin_text: "The document contained too little text to use",
  empty: "The fetched document was empty",
  blocked: "The publisher blocked the fetch",
  blocked_by_host: "The publisher's site blocked the fetch",
  fetch_error: "The fetch failed",
  unsupported_type: "The fetched file was not a text document",
};

/**
 * A backend reason code in plain words; an unknown snake_case code
 * de-snakes rather than rendering as a variable, anything else passes
 * through untouched.
 *
 * Args:
 *   code: The reason code.
 *
 * Returns:
 *   The sentence.
 */
export function humanReason(code: string): string {
  if (HUMAN_REASON[code] !== undefined) return HUMAN_REASON[code];
  if (/^[a-z0-9_]+$/.test(code)) {
    const phrase = code.replaceAll("_", " ");
    return phrase.charAt(0).toUpperCase() + phrase.slice(1);
  }
  return code;
}

/**
 * The hover on "Abstract only" and "Title only": why the full text wasn't
 * read, in plain words. `null` for a source read in full (no hover needed).
 *
 * Args:
 *   item: The source's read state and the reason its text is missing.
 *
 * Returns:
 *   The sentence, or null.
 */
export function readDepthHint(item: Pick<DepthSource, "read_in_full" | "status" | "status_reason" | "abstract">): string | null {
  if (item.read_in_full) return null;
  const read = item.abstract?.trim() ? "the abstract" : "the title";
  if (item.status === "unavailable") {
    return item.status_reason
      ? `${humanReason(item.status_reason)} — only ${read} was read.`
      : `The full text couldn't be obtained — only ${read} was read.`;
  }
  return item.abstract?.trim()
    ? "The full text hasn't been collected — screening and appraisal used the title and abstract."
    : "The full text hasn't been collected and there is no abstract — screening and appraisal used the title.";
}

// ---------------------------------------------------------------------------
// Evidence type
// ---------------------------------------------------------------------------

/**
 * An evidence type in sentence case (round 10, C6): the classifier's labels
 * are Title Case ("Systematic Review and Meta-Analysis"), the page writes
 * them as a sentence would ("Systematic review and meta-analysis").
 * Acronyms keep their capitals ("RCTs and quasi-experimental studies").
 * Display only: filters and links keep the classifier's own value.
 *
 * Args:
 *   type: The evidence type as the classifier labels it.
 *
 * Returns:
 *   The label in sentence case.
 */
export function evidenceTypeLabel(type: string): string {
  let first = true;
  return type.trim().replace(/\p{L}[\p{L}']*/gu, (word) => {
    const acronym = /^\p{Lu}{2,}s?$/u.test(word);
    const out = acronym
      ? word
      : first
        ? word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
        : word.toLowerCase();
    first = false;
    return out;
  });
}

// ---------------------------------------------------------------------------
// The judge's verdict on a citation
// ---------------------------------------------------------------------------

/** The grounding tiers' labels (demo ui.tsx TIER_LABEL, locked). An unknown
 *  tier has none, so its raw value never renders. */
export const TIER_LABEL: Record<string, string> = {
  tier_1: "Tier 1 · direct quote",
  tier_2: "Tier 2 · grounded",
  tier_3: "Tier 3 · supported",
  tier_4: "Tier 4 · reasoning",
  unsupported_mis_cited: "Unsupported",
};

/** What each grounding tier means, for a verdict that gave no words. */
export const TIER_TEXT: Record<string, string> = {
  tier_1: "Direct quote, verified against the source",
  tier_2: "Grounded in a specific passage",
  tier_3: "Supported across passages",
  tier_4: "Reasoning from the evidence, not a quote",
  unsupported_mis_cited: "Failed verification — flagged, never hidden",
};

/** The word for a citation the judge has not checked. */
export const UNCHECKED = "Unchecked";

/**
 * Why a citation is unchecked: awaiting the check, or the check could not
 * run (chat).
 *
 * Args:
 *   checkFailed: True when the evidence check could not run.
 *
 * Returns:
 *   The sentence.
 */
export function uncheckedWords(checkFailed: boolean): string {
  return checkFailed ? "The evidence check could not run for this answer" : "Awaiting evidence check";
}

/** The unchecked verdict on one line, for a chip or a hover's status line. */
export function uncheckedLabel(checkFailed: boolean): string {
  return checkFailed ? `${UNCHECKED} · check unavailable` : `${UNCHECKED} · awaiting evidence check`;
}

/** What the judge decided about one citation: its verdict as a Meta label,
 *  then its own words (or, when it gave none, what the verdict means). */
export interface CitationJudgement {
  label: string;
  words: string;
}

/**
 * The judge's verdict on a citation as words: the tier's label over the
 * judge's own rationale, or what the tier means when it gave none. No tier
 * yet says it is unchecked (lead, round 12); an unknown tier says nothing.
 *
 * Args:
 *   tier: The judge's tier, or null/undefined before the check.
 *   rationale: The judge's own words, when it gave any.
 *   checkFailed: True when the evidence check could not run (chat).
 *
 * Returns:
 *   The label and words, or null for an unknown tier.
 */
export function citationJudgement(
  tier: string | null | undefined,
  rationale: string | null | undefined,
  checkFailed = false,
): CitationJudgement | null {
  if (tier == null) return { label: UNCHECKED, words: uncheckedWords(checkFailed) };
  if (TIER_LABEL[tier] === undefined) return null;
  const own = typeof rationale === "string" && rationale.trim() !== "" ? rationale : null;
  return { label: TIER_LABEL[tier], words: own ?? TIER_TEXT[tier] };
}
