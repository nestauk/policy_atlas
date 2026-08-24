import { useState } from "react";

import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import {
  backendLabel,
  CHECK_IN_SEARCH_HEADING,
  CHECK_IN_SECTIONS_HEADING,
  checkInGroupsHeading,
  checkInReadingListHeading,
  checkInThemesHeading,
} from "./checkInPresentation";

/** One staged P2 theme rename (batched into the single check-in response). */
export interface ThemeRename {
  theme_id: string;
  name: string;
}

/**
 * One displayed P4 section row ({title, focus} — the steering grammar).
 * `group_ids` is an optional opaque section→group binding the backend may
 * attach; rows without it stay `{title, focus}` exactly as before. Edits
 * must carry it through unchanged — title/focus edits never strip it.
 */
export interface SectionRow {
  title: string;
  focus: string;
  group_ids?: string[];
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const strings = value.filter((entry): entry is string => typeof entry === "string");
  return strings.length > 0 ? strings : undefined;
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

/** Parse the P4 bundle's proposed ordinary sections, fail-soft. */
export function proposedSections(bundle: Record<string, unknown> | null): SectionRow[] {
  const proposal = record(bundle?.proposal) ?? bundle;
  const rows = asArray(proposal?.proposed_sections);
  const sections: SectionRow[] = [];
  for (const row of rows) {
    const entry = record(row);
    const title = asString(entry?.title);
    const focus = asString(entry?.focus);
    const group_ids = asStringArray(entry?.group_ids);
    if (title !== null && focus !== null) {
      sections.push(group_ids !== undefined ? { title, focus, group_ids } : { title, focus });
    }
  }
  return sections;
}

function ListBlock({
  heading,
  children,
}: {
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-3 border border-line bg-paper-2 px-3 py-2.5">
      <p className="text-caption font-bold uppercase tracking-[0.06em] text-grey">{heading}</p>
      {children}
    </div>
  );
}

/**
 * The typed per-point bundle display (028 strand 14; binding record
 * checkin-taxonomy.html): renders exactly what the projection carries —
 * P1 {backends, queries, sample_titles} · P2 {themes} (with ✎ rename) ·
 * P3 {shortlist} · Groups {groups} · P4 {proposed_sections} (with inline
 * ✎/×/+ editing). Shape-driven: absent shapes render nothing.
 */
export function CheckInBundle({
  bundle,
  stagedRenames,
  onStageRename,
  editedSections,
  onEditSections,
}: {
  bundle: Record<string, unknown> | null;
  stagedRenames: ThemeRename[];
  onStageRename: (rename: ThemeRename) => void;
  /** Null until the user edits; then the full displayed list, edited. */
  editedSections: SectionRow[] | null;
  onEditSections: (sections: SectionRow[]) => void;
}) {
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameText, setRenameText] = useState("");
  const [editingRow, setEditingRow] = useState<number | null>(null);
  const [rowTitle, setRowTitle] = useState("");
  const [rowFocus, setRowFocus] = useState("");
  const [adding, setAdding] = useState(false);

  if (bundle === null) return null;

  const backends = asArray(bundle.backends)
    .map((entry) => {
      const row = record(entry);
      const backend = asString(row?.backend);
      const count = asNumber(row?.count);
      return backend !== null && count !== null ? { backend, count } : null;
    })
    .filter((row): row is { backend: string; count: number } => row !== null);
  const queries = asArray(bundle.queries).map(asString).filter((q): q is string => q !== null);
  const sampleTitles = asArray(bundle.sample_titles)
    .map(asString)
    .filter((t): t is string => t !== null);
  const themes = asArray(bundle.themes)
    .map((entry) => {
      const row = record(entry);
      const theme_id = asString(row?.theme_id);
      const name = asString(row?.name);
      const size = asNumber(row?.size);
      return name !== null ? { theme_id, name, size } : null;
    })
    .filter((row): row is { theme_id: string | null; name: string; size: number | null } => row !== null);
  const shortlist = asArray(bundle.shortlist)
    .map((entry) => {
      const row = record(entry);
      const title = asString(row?.title);
      return title !== null ? { title, stratum: asString(row?.stratum) } : null;
    })
    .filter((row): row is { title: string; stratum: string | null } => row !== null);
  const groups = asArray(bundle.groups)
    .map((entry) => {
      const row = record(entry);
      const name = asString(row?.name);
      return name !== null ? { name, size: asNumber(row?.size) } : null;
    })
    .filter((row): row is { name: string; size: number | null } => row !== null);
  const sections = editedSections ?? proposedSections(bundle);

  return (
    <div>
      {backends.length > 0 && (
        <ListBlock heading={CHECK_IN_SEARCH_HEADING}>
          <p className="mt-1 text-body text-navy">
            {backends
              .map(({ backend, count }) => `${scrub(backendLabel(backend) ?? backend)} ${count}`)
              .join(" · ")}
            {queries.length > 0 ? ` · from ${queries.length === 1 ? "1 query" : `${queries.length} queries`}` : ""}
          </p>
          {sampleTitles.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {sampleTitles.slice(0, 5).map((title) => (
                <li key={title} className="truncate text-body text-ink">
                  {scrub(title)}
                </li>
              ))}
            </ul>
          )}
          {queries.length > 0 && (
            <details className="mt-1.5 text-caption text-grey">
              <summary className="cursor-pointer">The queries used</summary>
              <ul className="mt-1 space-y-0.5">
                {queries.map((query) => (
                  <li key={query} className="text-ink">
                    {scrub(query)}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </ListBlock>
      )}

      {themes.length > 0 && (
        <ListBlock heading={checkInThemesHeading(themes.length)}>
          <ul className="mt-1.5 space-y-1">
            {themes.map((theme) => {
              const staged = stagedRenames.find((rename) => rename.theme_id === theme.theme_id);
              const shown = staged?.name ?? theme.name;
              return (
                <li key={theme.name} className="flex items-baseline gap-2 text-body text-ink">
                  {renaming === theme.theme_id && theme.theme_id !== null ? (
                    <span className="flex flex-1 items-center gap-1.5">
                      <input
                        value={renameText}
                        onChange={(event) => setRenameText(event.target.value)}
                        aria-label={`New name for ${theme.name}`}
                        className="flex-1 border border-line-2 px-1.5 py-0.5 text-body"
                      />
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          if (renameText.trim() !== "") {
                            onStageRename({ theme_id: theme.theme_id ?? "", name: renameText.trim() });
                          }
                          setRenaming(null);
                        }}
                      >
                        Rename
                      </Button>
                    </span>
                  ) : (
                    <>
                      <span className="min-w-0 flex-1 truncate">
                        {scrub(shown)}
                        {staged !== undefined && (
                          <span className="ml-1 text-grey">(renamed — applies with your answer)</span>
                        )}
                      </span>
                      {theme.size !== null && <span className="shrink-0 text-grey">· {theme.size}</span>}
                      {theme.theme_id !== null && (
                        <button
                          type="button"
                          aria-label={`Rename ${theme.name}`}
                          className="shrink-0 cursor-pointer text-blue hover:text-navy"
                          onClick={() => {
                            setRenaming(theme.theme_id);
                            setRenameText(shown);
                          }}
                        >
                          ✎ rename
                        </button>
                      )}
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        </ListBlock>
      )}

      {shortlist.length > 0 && (
        <ListBlock heading={checkInReadingListHeading(shortlist.length)}>
          <ul className="mt-1.5 space-y-0.5">
            {shortlist.slice(0, 6).map((row) => (
              <li key={row.title} className="flex items-baseline gap-2 text-body text-ink">
                <span className="min-w-0 flex-1 truncate">{scrub(row.title)}</span>
                {row.stratum !== null && <span className="shrink-0 text-grey">· {scrub(row.stratum)}</span>}
              </li>
            ))}
          </ul>
          {shortlist.length > 6 && (
            <p className="mt-1 text-body text-grey">…and {shortlist.length - 6} more</p>
          )}
        </ListBlock>
      )}

      {groups.length > 0 && (
        <ListBlock heading={checkInGroupsHeading(groups.length)}>
          <ul className="mt-1.5 space-y-0.5">
            {groups.slice(0, 6).map((group) => (
              <li key={group.name} className="flex items-baseline gap-2 text-body text-ink">
                <span className="min-w-0 flex-1 truncate">{scrub(group.name)}</span>
                {group.size !== null && (
                  <span className="shrink-0 text-grey">
                    · {group.size === 1 ? "1 finding" : `${group.size} findings`}
                  </span>
                )}
              </li>
            ))}
          </ul>
          {groups.length > 6 && <p className="mt-1 text-body text-grey">…and {groups.length - 6} more</p>}
        </ListBlock>
      )}

      {sections.length > 0 && (
        <ListBlock heading={CHECK_IN_SECTIONS_HEADING}>
          <ul className="mt-1.5 space-y-1">
            {sections.map((section, index) => (
              <li key={`${section.title}-${index}`} className="flex items-baseline gap-2 text-body text-ink">
                {editingRow === index ? (
                  <span className="flex flex-1 flex-col gap-1">
                    <input
                      value={rowTitle}
                      maxLength={200}
                      onChange={(event) => setRowTitle(event.target.value)}
                      aria-label="Section title"
                      className="border border-line-2 px-1.5 py-0.5 text-body"
                    />
                    <input
                      value={rowFocus}
                      maxLength={200}
                      onChange={(event) => setRowFocus(event.target.value)}
                      aria-label="What it covers"
                      className="border border-line-2 px-1.5 py-0.5 text-body"
                    />
                    <span className="flex gap-1.5">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          if (rowTitle.trim() !== "") {
                            const next = [...sections];
                            next[index] = {
                              ...section,
                              title: rowTitle.trim(),
                              focus: rowFocus.trim() || section.focus,
                            };
                            onEditSections(next);
                          }
                          setEditingRow(null);
                        }}
                      >
                        Keep edit
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setEditingRow(null)}>
                        Cancel
                      </Button>
                    </span>
                  </span>
                ) : (
                  <>
                    <span className="min-w-0 flex-1">{scrub(section.title)}</span>
                    <button
                      type="button"
                      aria-label={`Edit section ${section.title}`}
                      className="shrink-0 cursor-pointer text-blue hover:text-navy"
                      onClick={() => {
                        setEditingRow(index);
                        setRowTitle(section.title);
                        setRowFocus(section.focus);
                      }}
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      aria-label={`Remove section ${section.title}`}
                      className="shrink-0 cursor-pointer text-blue hover:text-navy"
                      onClick={() => onEditSections(sections.filter((_, i) => i !== index))}
                    >
                      ×
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-body text-grey">
            Key findings opens the report and Conclusions closes it — those are structural and
            stay.
          </p>
          {adding ? (
            <span className="mt-1.5 flex flex-col gap-1">
              <input
                value={rowTitle}
                maxLength={200}
                onChange={(event) => setRowTitle(event.target.value)}
                aria-label="New section title"
                placeholder="Section title"
                className="border border-line-2 px-1.5 py-0.5 text-body"
              />
              <input
                value={rowFocus}
                maxLength={200}
                onChange={(event) => setRowFocus(event.target.value)}
                aria-label="What the new section covers"
                placeholder="What it covers"
                className="border border-line-2 px-1.5 py-0.5 text-body"
              />
              <span className="flex gap-1.5">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    if (rowTitle.trim() !== "" && rowFocus.trim() !== "") {
                      onEditSections([...sections, { title: rowTitle.trim(), focus: rowFocus.trim() }]);
                      setRowTitle("");
                      setRowFocus("");
                      setAdding(false);
                    }
                  }}
                >
                  Add section
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setAdding(false)}>
                  Cancel
                </Button>
              </span>
            </span>
          ) : (
            <button
              type="button"
              className="mt-1.5 cursor-pointer text-meta font-semibold text-blue hover:text-navy"
              onClick={() => {
                setRowTitle("");
                setRowFocus("");
                setAdding(true);
              }}
            >
              + Add a section
            </button>
          )}
        </ListBlock>
      )}
    </div>
  );
}
