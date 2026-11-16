import { useState } from "react";

import type { LiveClaim, LiveSection, RunStreamState } from "../../store";
import { useRevealedText } from "../streamPacing";

/*
 * The theory of change's report while it is written (task 054's 058
 * alignment, S6, S7, A13). The server streams today's one report call
 * through Evidence search's live frames: a skeleton of the page's parts,
 * then each field in the order the model writes it, each in its page place.
 * Nothing here changes the report's content: the live view shows the
 * model's words as they arrive, and the committed report from `GET /toc`
 * replaces it in place.
 */

/** The page's parts, as the skeleton names them. The first four are the
 *  header's, in this order (`report_stream.PAGE_PARTS`); the others carry
 *  their heading as their title. */
export type TocPartKey =
  | "title"
  | "verdict"
  | "question"
  | "in_brief"
  | "summary"
  | "pathways"
  | "how_it_could_fail"
  | "tests"
  | "found_routes"
  | "supporting_activities"
  | "assumptions"
  | "references";

const HEADER_KEYS: readonly TocPartKey[] = ["title", "verdict", "question", "in_brief"];

/** The report's sections by the heading the page and the skeleton share. */
export const SECTION_KEYS: Readonly<Record<string, TocPartKey>> = {
  Summary: "summary",
  Pathways: "pathways",
  "How it could fail": "how_it_could_fail",
  "What to test first": "tests",
  "How it could be expanded": "found_routes",
  "Supporting activities": "supporting_activities",
  Assumptions: "assumptions",
  References: "references",
};

/** The parts whose fields are lists: each item arrives whole (a card). */
const LIST_PARTS: ReadonlySet<TocPartKey> = new Set(["pathways", "tests", "found_routes", "supporting_activities", "assumptions"]);

/** Whether a part is a list of items. */
export function isListPart(key: TocPartKey): boolean {
  return LIST_PARTS.has(key);
}

/**
 * The stream's live sections as the report's parts.
 *
 * Args:
 *   sections: The stream's live sections (`RunStreamState.liveSections`).
 *
 * Returns:
 *   Each part the skeleton named, by its key. Empty when the stream holds
 *   no report.
 */
export function tocParts(sections: RunStreamState["liveSections"]): Map<TocPartKey, LiveSection> {
  const parts = new Map<TocPartKey, LiveSection>();
  for (const section of Object.values(sections)) {
    // The header's parts hold the skeleton's first four places, always
    // (an optional part is only ever a section); a part that closed empty
    // (a verdict whose call failed) leaves the store, never its place.
    const key = section.index < HEADER_KEYS.length ? HEADER_KEYS[section.index] : SECTION_KEYS[section.title];
    if (key !== undefined) parts.set(key, section);
  }
  return parts;
}

/** A completed list part's text ("**Title**\nText", items apart by a blank
 *  line) back into its items. */
function listItems(prose: string): { title: string; prose: string }[] {
  return prose
    .split(/\n[ \t]*\n/)
    .map((block) => block.trim())
    .filter((block) => block !== "")
    .map((block) => {
      const head = /^\*\*(.+?)\*\*\n?/.exec(block);
      return head === null ? { title: "", prose: block } : { title: head[1], prose: block.slice(head[0].length) };
    });
}

/** A list item's title without the full stop or colon it may close on. */
function itemTitle(title: string): string {
  return title.trim().replace(/[.:]$/, "");
}

/**
 * A part's text so far: its draft while it is written, its prose once it
 * closes, the same words either way (there is no claim check here, so
 * nothing is revised). A list part reads one item a line, its title leading
 * ("Title: text"), as the live page lays a list out.
 *
 * Args:
 *   key: The part.
 *   section: Its live section.
 *
 * Returns:
 *   The part's text.
 */
export function partText(key: TocPartKey, section: LiveSection): string {
  if (!isListPart(key)) return section.state === "filled" ? (section.prose ?? "") : (section.draft ?? "");
  const items = section.state === "filled" ? listItems(section.prose ?? "") : (section.cards ?? []);
  return items.map((item) => (item.title.trim() !== "" ? `${itemTitle(item.title)}: ${item.prose}` : item.prose)).join("\n");
}

/** A source number written in the text: "[3]", "[3, 5]" or "[3–5]", with the
 *  space before it. */
const CITATION = /\s*\[(\d+(?:\s*[,–-]\s*\d+)*)\]/g;

/**
 * The model's "[n]" markers as the shared live page's pending chips (S5):
 * the numbers leave the text, and each becomes a claim ending on the word
 * before it, which the page shows as the muted "[·]" with the source's name
 * on hover. A number the sources frame does not name keeps the chip with no
 * name.
 *
 * Args:
 *   text: The part's text so far.
 *   sources: Each numbered source's short name, by its number.
 *
 * Returns:
 *   The text without its numbers, and the claims, in code points.
 */
export function pendingCitations(text: string, sources: ReadonlyMap<string, string>): { text: string; claims: LiveClaim[] } {
  const claims: LiveClaim[] = [];
  let out = "";
  let length = 0;
  let from = 0;
  for (const match of text.matchAll(CITATION)) {
    const before = text.slice(from, match.index);
    out += before;
    length += Array.from(before).length;
    from = match.index + match[0].length;
    const numbers = match[1].split(/\s*[,–-]\s*/);
    if (length === 0) continue;
    claims.push({
      start: length - 1,
      end: length,
      sources: numbers.map((n) => ({ sourceId: n, title: sources.get(n) ?? `Source ${n}` })),
    });
  }
  out += text.slice(from);
  return { text: out, claims };
}

/**
 * The numbered sources the report draws on, kept across the parts: the
 * server sends them with every part as it opens and the store drops a
 * part's set when the part closes, so the page remembers each name it has
 * seen. Cleared with a new run.
 *
 * Args:
 *   runId: The run the stream follows.
 *   sections: The live sections.
 *
 * Returns:
 *   Each source's short name, by its number.
 */
export function useLiveSourceNames(runId: string | null, sections: readonly LiveSection[]): ReadonlyMap<string, string> {
  const [names, setNames] = useState<{ runId: string | null; byNumber: ReadonlyMap<string, string> }>(() => ({ runId, byNumber: new Map() }));
  const known = names.runId === runId ? names.byNumber : new Map<string, string>();
  const seen = sections.flatMap((section) => section.sources ?? []);
  if (names.runId !== runId || seen.some((source) => known.get(source.sourceId) !== source.title)) {
    const byNumber = new Map(known);
    for (const source of seen) byNumber.set(source.sourceId, source.title);
    setNames({ runId, byNumber });
    return byNumber;
  }
  return known;
}

/**
 * The part being written: the one whose words changed last, while it is
 * still open. Fields arrive one at a time, so one part at a time reads
 * "◆ Writing".
 *
 * Args:
 *   parts: The live parts.
 *
 * Returns:
 *   The part's key, or null between fields.
 */
export function useActivePart(parts: ReadonlyMap<TocPartKey, LiveSection>): TocPartKey | null {
  const lengths = [...parts.entries()].map(([key, section]) => [key, partText(key, section).length] as const);
  const signature = lengths.map(([key, length]) => `${key}:${length}`).join("|");
  const [track, setTrack] = useState<{ signature: string; lengths: ReadonlyMap<TocPartKey, number>; active: TocPartKey | null }>(() => ({
    signature,
    lengths: new Map(lengths),
    active: null,
  }));
  let active = track.active;
  if (track.signature !== signature) {
    for (const [key, length] of lengths) {
      if (length !== (track.lengths.get(key) ?? 0)) active = key;
    }
    setTrack({ signature, lengths: new Map(lengths), active });
  }
  if (active === null) return null;
  const section = parts.get(active);
  return section !== undefined && section.state !== "filled" ? active : null;
}

/** A header part's words as they are revealed (the title, the verdict
 *  line): paced as the report's words are, plain text. */
export function RevealedWords({ text }: { text: string }) {
  const revealed = useRevealedText(text);
  return <>{revealed.text}</>;
}
