/*
 * The reference line (task 058, round 12 consolidation): authors, year,
 * title, venue and address in the References' citation form, defined once
 * and imported by the report's References, the citation sheet, the source
 * dossier, the option card and the Markdown download.
 */

/** A source title that opens its dossier, as the report's References and
 *  most relevant sources show it: Navy, underlined in Line 2, the underline
 *  turning Navy on hover (round 10, finding 1). Shared with the option card
 *  (round 13): the References, the most relevant sources, the citation sheet and the option card. */
export const SOURCE_TITLE_LINK_CLASS =
  "text-navy underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 hover:decoration-navy";

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
