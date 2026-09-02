import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { useFunnel, useLandscape } from "../api/queries";
import { Link } from "react-router";
import { scrub } from "../lib/scrub";
import { REPORT_SECTION_HEADING_CLASS } from "./artefactPresentation";

/** Minimal section shape the outline consumes (mirrors SectionOut). */
export interface OutlineSection {
  title: string;
  role: "key_findings" | "case_studies" | "standard" | "conclusions";
  summary?: string | null;
  summary_status?: "pending" | "verified" | "failed" | null;
  blocks?: Array<{ prose: string }> | null;
}

/**
 * The one-line summary a collapsed section shows (028 strand 5/13):
 * the VERIFIED block summary where one exists; the section's own first
 * sentence as the honest fallback — rendered unmarked, indistinguishable
 * from a verified summary (owner ruling, batch 12: the checked/fallback
 * distinction is provenance for reviewers, not users). `focus` never
 * renders (live data shows it is the writing brief). Never generated at
 * render time.
 */
export function sectionSummary(section: OutlineSection): { text: string } | null {
  if (
    section.summary != null &&
    section.summary !== "" &&
    section.summary_status === "verified"
  ) {
    return { text: section.summary };
  }
  const prose = section.blocks?.[0]?.prose ?? "";
  if (prose === "") return null;
  const line = prose.split("\n").find((candidate) => candidate.trim() !== "") ?? "";
  const sentence = /^.*?[.!?](?=\s|$)/.exec(line.trim())?.[0] ?? line.trim();
  return sentence === "" ? null : { text: sentence };
}

/** Slug id for a section heading — the sidebar's scroll target. */
export function sectionAnchor(title: string, index: number): string {
  return `section-${index}-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40)}`;
}

const OPEN_SECTION_EVENT = "artefact-open-section";
/** Matches the per-section Expand + / Collapse − affordance. */
export const SECTION_EXPAND_LINK_CLASS = "print-hide shrink-0 text-meta font-bold text-blue";
/** Leave a little air under the scrollport top after a contents jump. */
const SECTION_SCROLL_OFFSET_PX = 8;
/** Ignore the spy while a click-driven scroll is settling. */
const SPY_LOCK_MS = 500;

function hashTargets(id: string): boolean {
  return decodeURIComponent(window.location.hash.replace(/^#/, "")) === id;
}

function nearestScrollRoot(start: HTMLElement): HTMLElement | null {
  let node: HTMLElement | null = start.parentElement;
  while (node != null && node !== document.body) {
    const overflowY = getComputedStyle(node).overflowY;
    if (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") {
      return node;
    }
    node = node.parentElement;
  }
  return null;
}

/** Scroll the report pane — not the window — so the section sits at the top. */
function scrollSectionIntoView(id: string): void {
  const target = document.getElementById(id);
  if (target == null) return;
  const root = nearestScrollRoot(target);
  if (root == null) {
    target.scrollIntoView({ block: "start" });
    return;
  }
  const top =
    target.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop;
  root.scrollTo({ top: Math.max(0, top - SECTION_SCROLL_OFFSET_PX) });
}

/** Contents-nav click: record the hash without the browser scrolling to a
 *  still-collapsed heading, then tell the matching section to expand. */
function requestOpenSection(id: string): void {
  const next = `#${id}`;
  if (window.location.hash !== next) {
    history.replaceState(
      null,
      "",
      `${window.location.pathname}${window.location.search}${next}`,
    );
  }
  window.dispatchEvent(new CustomEvent(OPEN_SECTION_EVENT, { detail: id }));
}

interface FullReportExpandControl {
  expanded: boolean;
  revision: number;
  setAllExpanded: (expanded: boolean) => void;
}

const FullReportExpandContext = createContext<FullReportExpandControl | null>(null);

/** Syncs collapsible full-report blocks to the Expand all / Collapse all control. */
export function FullReportExpandProvider({ children }: { children: React.ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  const [revision, setRevision] = useState(0);
  const setAllExpanded = useCallback((next: boolean) => {
    if (!next && window.location.hash !== "") {
      history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    }
    setExpanded(next);
    setRevision((value) => value + 1);
  }, []);
  const value = useMemo(
    () => ({ expanded, revision, setAllExpanded }),
    [expanded, revision, setAllExpanded],
  );
  return <FullReportExpandContext.Provider value={value}>{children}</FullReportExpandContext.Provider>;
}

/** Expand all / Collapse all beside the Full report heading. */
export function FullReportExpandAllButton() {
  const control = useContext(FullReportExpandContext);
  if (control == null) return null;
  const { expanded, setAllExpanded } = control;
  return (
    <button
      type="button"
      onClick={() => setAllExpanded(!expanded)}
      className={`${SECTION_EXPAND_LINK_CLASS} cursor-pointer`}
    >
      {expanded ? "Collapse all" : "Expand all"}
    </button>
  );
}

/** Expand when the contents sidebar or a hash URL points at this section,
 *  then scroll — even if the section was already open. */
export function useOpenWhenNavigated(id: string, setOpen: (open: boolean) => void): void {
  const [navTick, setNavTick] = useState(0);
  useEffect(() => {
    const go = () => {
      setOpen(true);
      setNavTick((tick) => tick + 1);
    };
    const onSidebar = (event: Event) => {
      if ((event as CustomEvent<string>).detail === id) go();
    };
    const onHash = () => {
      if (hashTargets(id)) go();
    };
    if (hashTargets(id)) go();
    window.addEventListener(OPEN_SECTION_EVENT, onSidebar);
    window.addEventListener("hashchange", onHash);
    return () => {
      window.removeEventListener(OPEN_SECTION_EVENT, onSidebar);
      window.removeEventListener("hashchange", onHash);
    };
  }, [id, setOpen]);

  useLayoutEffect(() => {
    if (navTick === 0) return;
    scrollSectionIntoView(id);
  }, [navTick, id]);
}

/** Scroll when the contents sidebar or hash targets a block that is always visible. */
export function useScrollWhenNavigated(id: string): void {
  useOpenWhenNavigated(id, () => {});
}

/** Open a collapsed section when the browser is about to print, so the PDF
 *  contains the full report rather than the on-screen collapsed summaries. */
export function useExpandForPrint(setOpen: (open: boolean) => void): void {
  useEffect(() => {
    const expand = () => setOpen(true);
    window.addEventListener("beforeprint", expand);
    return () => window.removeEventListener("beforeprint", expand);
  }, [setOpen]);
}

/** Expand or collapse when the full-report Expand all / Collapse all control is used. */
export function useExpandAll(setOpen: (open: boolean) => void, enabled = true): void {
  const control = useContext(FullReportExpandContext);
  useEffect(() => {
    if (!enabled || control == null || control.revision === 0) return;
    setOpen(control.expanded);
  }, [control, enabled, setOpen]);
}

export type SidebarEntry =
  | { id: string; title: string }
  | { kind: "part"; id: string; title: string };

function sidebarNavEntries(entries: SidebarEntry[]): Array<{ id: string; title: string; part: boolean }> {
  return entries.map((entry) =>
    "kind" in entry
      ? { id: entry.id, title: entry.title, part: true }
      : { id: entry.id, title: entry.title, part: false },
  );
}

function requestScrollToSection(id: string): void {
  const next = `#${id}`;
  if (window.location.hash !== next) {
    history.replaceState(null, "", `${window.location.pathname}${window.location.search}${next}`);
  }
  scrollSectionIntoView(id);
}

/**
 * Sticky contents sidebar with scroll-spy (mock-up's sidebar variant; built
 * for the real section-list shape — long question-specific titles wrap).
 * Stacks above the report on small screens so the outline stays reachable
 * instead of disappearing below a breakpoint.
 *
 * Entries with `kind: "part"` render as clickable part headings (Executive
 * summary, Full report) that scroll to the matching anchor on the page.
 */
export function ContentsSidebar({
  entries,
}: {
  entries: SidebarEntry[];
}) {
  const navEntries = sidebarNavEntries(entries);
  const [activeId, setActiveId] = useState<string | null>(navEntries[0]?.id ?? null);
  const spyLockUntil = useRef(0);

  useEffect(() => {
    const list = navEntries;
    const first = list
      .map((entry) => document.getElementById(entry.id))
      .find((element): element is HTMLElement => element != null);
    if (first == null) return undefined;
    const root = nearestScrollRoot(first);
    const checkpoint = () => {
      if (Date.now() < spyLockUntil.current) return;
      const scroller = root;
      const line = scroller != null ? scroller.getBoundingClientRect().top + 16 : 16;
      let current = list[0]?.id ?? null;
      for (const entry of list) {
        const element = document.getElementById(entry.id);
        if (element == null) continue;
        if (element.getBoundingClientRect().top <= line) current = entry.id;
      }
      if (scroller != null) {
        const maxScroll = scroller.scrollHeight - scroller.clientHeight;
        if (maxScroll > 32 && scroller.scrollTop >= maxScroll - 8) {
          current = list.at(-1)?.id ?? current;
        }
      }
      if (current != null) setActiveId(current);
    };
    const scroller: HTMLElement | Window = root ?? window;
    scroller.addEventListener("scroll", checkpoint, { passive: true });
    checkpoint();
    return () => scroller.removeEventListener("scroll", checkpoint);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries]);

  return (
    <nav
      aria-label="Contents"
      className="mb-6 w-full shrink-0 pt-4 md:sticky md:top-0 md:mb-0 md:max-h-[calc(100svh-10rem)] md:w-56 md:self-start md:overflow-y-auto md:pr-4"
    >
      <ul className="space-y-1 border-l border-line">
        {entries.map((entry, index) =>
          "kind" in entry ? (
            <li key={entry.id} className={index === 0 ? "pb-0.5" : "pb-0.5 pt-3"}>
              <a
                href={`#${entry.id}`}
                aria-current={activeId === entry.id ? "location" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  spyLockUntil.current = Date.now() + SPY_LOCK_MS;
                  setActiveId(entry.id);
                  requestScrollToSection(entry.id);
                }}
                className={`block border-l-2 py-0.5 pl-3 text-meta font-bold uppercase tracking-[0.06em] leading-snug hover:text-navy ${
                  activeId === entry.id
                    ? "border-l-blue text-navy"
                    : "border-l-transparent text-grey"
                }`}
              >
                {scrub(entry.title)}
              </a>
            </li>
          ) : (
            <li key={entry.id}>
              <a
                href={`#${entry.id}`}
                aria-current={activeId === entry.id ? "location" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  spyLockUntil.current = Date.now() + SPY_LOCK_MS;
                  setActiveId(entry.id);
                  requestOpenSection(entry.id);
                }}
                className={`block border-l-2 py-0.5 pl-3 text-body leading-snug hover:text-navy ${
                  activeId === entry.id
                    ? "border-l-blue font-semibold text-navy"
                    : "border-l-transparent text-grey"
                }`}
              >
                {scrub(entry.title)}
              </a>
            </li>
          ),
        )}
      </ul>
    </nav>
  );
}

/**
 * A collapsible artefact section (028 strand 5): real button, aria-expanded,
 * title + one-line summary visible while collapsed. Key findings is NOT
 * collapsible — it always renders in full. The fallback summary carries its
 * marker; a failed summary never renders as a summary.
 */
export function SectionDisclosure({
  id,
  section,
  defaultOpen,
  collapsible,
  children,
}: {
  id: string;
  section: OutlineSection;
  defaultOpen: boolean;
  collapsible: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  useOpenWhenNavigated(id, setOpen);
  useExpandForPrint(setOpen);
  useExpandAll(setOpen, collapsible);
  const summary = sectionSummary(section);
  const expanded = !collapsible || open;

  return (
    <section
      id={id}
      className={section.role === "conclusions" ? "mb-9 border-t border-line pt-6" : "mb-9"}
    >
      {collapsible ? (
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setOpen((value) => !value)}
          className="flex w-full cursor-pointer items-baseline gap-2 text-left"
        >
          <h2 className={`flex-1 ${REPORT_SECTION_HEADING_CLASS}`}>
            {scrub(section.title)}
          </h2>
          <span aria-hidden="true" className={SECTION_EXPAND_LINK_CLASS}>
            {expanded ? "Collapse −" : "Expand +"}
          </span>
        </button>
      ) : (
        <h2 className={REPORT_SECTION_HEADING_CLASS}>{scrub(section.title)}</h2>
      )}
      {/* Fallback (first-sentence) summaries render unmarked — the checked/
          fallback distinction is provenance for reviewers, not users
          (owner, 2026-08-05). */}
      {!expanded && summary !== null && (
        <p className="mt-1.5 max-w-prose-measure text-lead text-grey">{scrub(summary.text)}</p>
      )}
      {expanded && <div className="mt-3 space-y-4">{children}</div>}
    </section>
  );
}

/**
 * "How the evidence was gathered" (028 strand 10, fork C hybrid): a
 * collapsible, CITED-scoped section — distributions over only the sources
 * the report cites, with the compact whole-search funnel line and the
 * Landscape pointer for the full corpus. Counts label "Documents".
 */
export function GatheredSection({ projectId, id }: { projectId: string; id: string }) {
  const [open, setOpen] = useState(false);
  useOpenWhenNavigated(id, setOpen);
  useExpandForPrint(setOpen);
  useExpandAll(setOpen);
  const landscape = useLandscape(projectId, "cited");
  const funnel = useFunnel(projectId);
  const cited = landscape.data;
  const distributions = useMemo(() => {
    if (cited === undefined) return [];
    const rows: Array<{ label: string; entries: Array<[string, number]> }> = [];
    const types = Object.entries(cited.evidence_types ?? {}).sort(([, a], [, b]) => b - a);
    if (types.length > 0) rows.push({ label: "Evidence types", entries: types });
    const years = Object.entries(cited.years ?? {}).sort(([a], [b]) => a.localeCompare(b));
    if (years.length > 0) rows.push({ label: "Publication years", entries: years });
    const places = Object.entries(cited.geographies ?? {}).sort(([, a], [, b]) => b - a);
    if (places.length > 0) rows.push({ label: "Where published", entries: places });
    return rows;
  }, [cited]);

  const funnelLine =
    funnel.data !== undefined &&
    typeof funnel.data.found === "number" &&
    typeof funnel.data.relevant === "number" &&
    typeof funnel.data.cited === "number"
      ? `${funnel.data.found} found → ${funnel.data.relevant} included → ${funnel.data.cited} cited`
      : null;

  if (landscape.isError || (cited !== undefined && (cited.themes ?? []).length === 0 && distributions.length === 0)) {
    return null;
  }

  return (
    <section id={id} className="mt-12 border-t border-line pt-6">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full cursor-pointer items-baseline gap-2 text-left"
      >
        <h2 className="flex-1 text-heading font-bold text-navy">
          How the evidence was gathered
        </h2>
        <span aria-hidden="true" className={SECTION_EXPAND_LINK_CLASS}>
          {open ? "Collapse −" : "Expand +"}
        </span>
      </button>
      {!open && funnelLine !== null && (
        <p className="mt-1.5 text-body text-grey">{funnelLine}</p>
      )}
      {open && (
        <div className="mt-3 space-y-4">
          {funnelLine !== null && (
            <p className="text-body text-navy">
              {funnelLine}
              <span className="text-grey">
                {" "}
                · this section covers only the cited sources —{" "}
                <Link to={`/projects/${projectId}/sources/landscape`} className="text-blue hover:underline">
                  the Landscape tab
                </Link>{" "}
                shows the whole search
              </span>
            </p>
          )}
          {distributions.map((row) => (
            <div key={row.label}>
              <p className="text-meta font-bold uppercase tracking-[0.06em] text-grey">{row.label}</p>
              <ul className="mt-1 space-y-0.5">
                {row.entries.slice(0, 8).map(([label, count]) => (
                  <li key={label} className="flex items-baseline gap-2 text-body text-navy">
                    <span className="min-w-0 flex-1 truncate">{scrub(label)}</span>
                    <span className="text-grey">{count === 1 ? "1 document" : `${count} documents`}</span>
                  </li>
                ))}
              </ul>
              {row.label === "Where published" && (
                <p className="mt-1 text-body text-grey">
                  {/* Task 031: the read model reads the publishing venue's country only —
                      never the authors' affiliations, and never where the study was set. */}
                  The country of the publishing venue, when the database reports it — not where
                  each study was set. Sources without one are counted as “Not reported”.
                </p>
              )}
            </div>
          ))}
          {(cited?.themes ?? []).length > 0 && (
            <div>
              <p className="text-meta font-bold uppercase tracking-[0.06em] text-grey">Key themes</p>
              <ul className="mt-1 space-y-0.5">
                {(cited?.themes ?? []).map((theme) => (
                  <li key={theme.name} className="flex items-baseline gap-2 text-body text-navy">
                    <span className="min-w-0 flex-1 truncate">{scrub(theme.name)}</span>
                    {theme.theme_id != null ? (
                      <Link
                        to={`/projects/${projectId}/sources/all?theme=${theme.theme_id}`}
                        className="shrink-0 text-caption text-blue hover:underline"
                      >
                        {theme.size === 1 ? "1 document →" : `${theme.size} documents →`}
                      </Link>
                    ) : (
                      <span className="shrink-0 text-caption text-grey">
                        {theme.size === 1 ? "1 document" : `${theme.size} documents`}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
