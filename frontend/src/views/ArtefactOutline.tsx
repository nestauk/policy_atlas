import { createContext, useCallback, useContext, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { flushSync } from "react-dom";
import { Link } from "react-router";

import { useFunnel, useLandscape } from "../api/queries";
import { scrub } from "../lib/scrub";
import { REPORT_SECTION_HEADING_CLASS } from "./artefactPresentation";
import { evidenceTypeLabel, FULL_TEXT } from "../ui/brand/evidence";
import { LABEL_CLASS } from "../ui/brand/label";
import { LINK_CLASS, QUIET_CONTROL_CLASS } from "../ui/brand/inlineActions";
import { ChevronIcon } from "../ui/brand/icons";
import { cn } from "../ui/brand/cn";
import { Collapse } from "../ui/motion/Collapse";

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
/** A small blue Meta link that hides in print (the longlist grid's "more"
 *  control). The report's disclosures use `DisclosureWord` instead. */
export const SECTION_EXPAND_LINK_CLASS = `${LINK_CLASS} print-hide shrink-0 text-meta`;

/** The heading level a report section takes: `h3` inside a part (Executive
 *  summary, Full report), `h2` on a page without parts (a baseline, the
 *  longlist) and for the end matter (References, the method). */
export type SectionHeadingLevel = 2 | 3;

/**
 * The report's one disclosure vocabulary (round 10, C7): the chevron, then
 * "Show" or "Hide", Grey Semibold Meta over a Line 2 underline that turns
 * Navy on hover, as the trace's "Show steps" and the search queries' "Show".
 * The chevron points right when shut and turns down as it opens (200 ms).
 * Decorative inside a disclosure button (its name is the heading), so
 * `aria-hidden`; it hides in print, where everything prints open.
 */
export function DisclosureWord({
  open,
  className,
  named = false,
}: {
  open: boolean;
  className?: string;
  /** The word names its own button (the phone's twin toggle). */
  named?: boolean;
}) {
  return (
    <span
      aria-hidden={named ? undefined : true}
      className={cn("print-hide inline-flex shrink-0 items-center gap-1 text-meta font-semibold text-grey", className)}
    >
      <ChevronIcon
        size={12}
        className={cn("shrink-0 transition-transform duration-200 ease-[var(--ease-out-strong)]", open && "rotate-90")}
      />
      <span className="underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 group-hover:text-navy group-hover:decoration-navy">
        {open ? "Hide" : "Show"}
      </span>
    </span>
  );
}

/**
 * A collapsible section's heading (round 10, finding 5): the GOV.UK
 * accordion pattern, a heading holding a button, so the heading stays in a
 * screen reader's list of headings and the button carries `aria-expanded`
 * (a heading inside a button is invalid, and Safari drops it from the
 * rotor). It looks as the section heading always has, with the disclosure
 * word at the right from `md` up.
 */
export function DisclosureHeading({
  level,
  open,
  onToggle,
  className,
  wordClassName,
  children,
}: {
  level: SectionHeadingLevel;
  open: boolean;
  onToggle: () => void;
  className?: string;
  /** Extra classes for the disclosure word (the swap's fade-in). */
  wordClassName?: string;
  children: React.ReactNode;
}) {
  const Heading = level === 3 ? "h3" : "h2";
  return (
    <Heading className={cn(REPORT_SECTION_HEADING_CLASS, className)}>
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="group flex w-full cursor-pointer items-baseline gap-3 text-left"
      >
        <span className="min-w-0 flex-1">{children}</span>
        <DisclosureWord open={open} className={cn("max-md:hidden", wordClassName)} />
      </button>
    </Heading>
  );
}
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
 *  still-collapsed heading, then tell the matching section to expand. The
 *  facts line's in-page links use it too. */
export function requestOpenSection(id: string): void {
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

/*
 * The report's expand state, one piece per task, in memory (owner, round
 * 12). A reader who watched the report being written finds its sections all
 * open and the control reading "Hide all"; a reader who opens a finished
 * report fresh finds them shut; moving between the task's tabs (Sources and
 * back) keeps whatever the reader left. Each tab is its own route, so the
 * state lives outside the page: `all` is what the Show all / Hide all
 * control last said, `sections` each section's own open state by its id.
 * The live page seeds it open (`seedReportExpanded`); leaving the task
 * forgets it (`useForgetReportExpandOnLeave`, called by the task shell). Not
 * localStorage: a page load is a fresh entry.
 */
interface ReportExpandState {
  all: boolean;
  sections: Record<string, boolean>;
}

const reportExpand = new Map<string, ReportExpandState>();
const reportExpandListeners = new Set<() => void>();

function notifyReportExpand(): void {
  for (const listener of reportExpandListeners) listener();
}

function subscribeReportExpand(listener: () => void): () => void {
  reportExpandListeners.add(listener);
  return () => reportExpandListeners.delete(listener);
}

/** The task whose expand state the report page reads and writes, or `null`
 *  where the page keeps its own (a page rendered on its own, as in tests). */
const ReportExpandContext = createContext<string | null>(null);

/** Scopes the report's sections to one task's remembered expand state. */
export function ReportExpandScope({ taskId, children }: { taskId: string; children: React.ReactNode }) {
  return <ReportExpandContext.Provider value={taskId === "" ? null : taskId}>{children}</ReportExpandContext.Provider>;
}

/** The reader is watching the report being written: when it is committed,
 *  every section is open and the control reads "Hide all". Safe to call
 *  during render (it is idempotent and notifies no one: the page that calls
 *  it re-renders its sections in the same pass). */
export function seedReportExpanded(taskId: string): void {
  if (taskId === "") return;
  reportExpand.set(taskId, { all: true, sections: {} });
}

/** Forget a task's expand state, so the next visit is a fresh entry. */
export function forgetReportExpand(taskId: string): void {
  if (reportExpand.delete(taskId)) notifyReportExpand();
}

/** For the task shell: forgets the task's report expand state when the
 *  reader leaves the task (another task, a list page), not when they move
 *  between its tabs. */
export function useForgetReportExpandOnLeave(taskId: string | undefined): void {
  useEffect(() => {
    if (taskId === undefined || taskId === "") return undefined;
    return () => forgetReportExpand(taskId);
  }, [taskId]);
}

/** A collapsible part of the report's open state, remembered for the task:
 *  a section the reader has seen keeps its state; one they have not takes
 *  the control's (`all`); with nothing remembered, `defaultOpen`. */
export function useRememberedOpen(
  id: string,
  defaultOpen: boolean,
): [boolean, React.Dispatch<React.SetStateAction<boolean>>] {
  const taskId = useContext(ReportExpandContext);
  const [open, setOpen] = useState(() => {
    const remembered = taskId === null ? undefined : reportExpand.get(taskId);
    return remembered === undefined ? defaultOpen : (remembered.sections[id] ?? remembered.all);
  });
  useEffect(() => {
    if (taskId === null) return;
    const remembered = reportExpand.get(taskId) ?? { all: false, sections: {} };
    reportExpand.set(taskId, { ...remembered, sections: { ...remembered.sections, [id]: open } });
  }, [taskId, id, open]);
  return [open, setOpen];
}

interface FullReportExpandControl {
  expanded: boolean;
  revision: number;
  setAllExpanded: (expanded: boolean) => void;
}

const FullReportExpandContext = createContext<FullReportExpandControl | null>(null);

/** Syncs collapsible full-report blocks to the Show all / Hide all control.
 *  Inside a `ReportExpandScope` the control's state is the task's
 *  remembered `all`; outside one it is the provider's own. */
export function FullReportExpandProvider({ children }: { children: React.ReactNode }) {
  const taskId = useContext(ReportExpandContext);
  const [ownExpanded, setOwnExpanded] = useState(false);
  const rememberedAll = useSyncExternalStore(subscribeReportExpand, () =>
    taskId === null ? null : (reportExpand.get(taskId)?.all ?? false),
  );
  const expanded = rememberedAll ?? ownExpanded;
  const [revision, setRevision] = useState(0);
  const setAllExpanded = useCallback(
    (next: boolean) => {
      if (!next && window.location.hash !== "") {
        history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
      }
      setOwnExpanded(next);
      if (taskId !== null) {
        const remembered = reportExpand.get(taskId) ?? { all: false, sections: {} };
        reportExpand.set(taskId, { ...remembered, all: next });
        notifyReportExpand();
      }
      setRevision((value) => value + 1);
    },
    [taskId],
  );
  const value = useMemo(
    () => ({ expanded, revision, setAllExpanded }),
    [expanded, revision, setAllExpanded],
  );
  return <FullReportExpandContext.Provider value={value}>{children}</FullReportExpandContext.Provider>;
}

/** "Show all" / "Hide all" beside the Full report heading (round 10, C7:
 *  the disclosure vocabulary, a quiet control at Meta). */
export function FullReportExpandAllButton() {
  const control = useContext(FullReportExpandContext);
  if (control == null) return null;
  const { expanded, setAllExpanded } = control;
  return (
    <button
      type="button"
      onClick={() => setAllExpanded(!expanded)}
      className={cn(QUIET_CONTROL_CLASS, "print-hide shrink-0 text-meta")}
    >
      {expanded ? "Hide all" : "Show all"}
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
 *  contains the full report rather than the on-screen collapsed summaries.
 *  `flushSync` is required: without it, `window.print()` can capture the
 *  still-collapsed DOM before React commits the expand. */
export function useExpandForPrint(setOpen: (open: boolean) => void): void {
  useEffect(() => {
    const expand = () => {
      flushSync(() => {
        setOpen(true);
      });
    };
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
 * for the real section-list shape — long question-specific titles wrap, in
 * full). From `md` up only; below it the page carries `MobileContents`
 * under its title block instead.
 *
 * Entries with `kind: "part"` render as clickable part headings (Executive
 * summary, Full report) that scroll to the matching anchor on the page.
 */
export function ContentsSidebar({
  entries,
}: {
  entries: SidebarEntry[];
}) {
  const navEntries = useMemo(() => sidebarNavEntries(entries), [entries]);
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
      // The current section is the last whose heading has passed a line a
      // quarter of the way down the pane (at most 160 px): a heading the
      // reader is reading under counts, not only one at the very top
      // (round 10, finding 6).
      const top = scroller != null ? scroller.getBoundingClientRect().top : 0;
      const height = scroller != null ? scroller.clientHeight : window.innerHeight;
      const line = top + Math.min(160, height * 0.25);
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
  }, [navEntries]);

  return (
    <nav
      aria-label="Contents"
      className="max-md:hidden mb-6 w-full shrink-0 pt-4 md:sticky md:top-0 md:mb-0 md:max-h-[calc(100svh-10rem)] md:w-56 md:self-start md:overflow-y-auto md:pr-4"
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
                className={`block border-l-2 py-0.5 pl-3 text-meta font-bold uppercase tracking-label leading-snug hover:text-navy ${
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

/** Below Tailwind's `md` (768 px). */
const NARROW_QUERY = "(max-width: 767.98px)";

function narrowNow(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.(NARROW_QUERY).matches === true;
}

function subscribeNarrow(onChange: () => void): () => void {
  const query = typeof window === "undefined" ? undefined : window.matchMedia?.(NARROW_QUERY);
  query?.addEventListener?.("change", onChange);
  return () => query?.removeEventListener?.("change", onChange);
}

/**
 * The contents on a phone (round 10, D3): a closed "Contents" disclosure
 * under the title block, below `md` only. Opened, it lists the same entries
 * as the sidebar; choosing one closes it and opens and scrolls to that
 * section, as the sidebar does. `ReportPage` places it.
 */
export function MobileContents({ entries }: { entries: SidebarEntry[] }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  // Mounted only below md, so a wide page carries one "Contents" landmark.
  const narrow = useSyncExternalStore(subscribeNarrow, narrowNow, () => false);
  if (!narrow) return null;
  const go = (entry: SidebarEntry) => {
    setOpen(false);
    if ("kind" in entry) requestScrollToSection(entry.id);
    else requestOpenSection(entry.id);
  };
  return (
    <nav aria-label="Contents" className="print-hide mb-8 border-y border-line md:hidden">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        onClick={() => setOpen((value) => !value)}
        className="group flex min-h-11 w-full cursor-pointer items-center gap-2 text-left"
      >
        <ChevronIcon
          size={12}
          className={cn("shrink-0 text-grey transition-transform duration-200 ease-[var(--ease-out-strong)]", open && "rotate-90")}
        />
        <span className={cn(LABEL_CLASS, "group-hover:text-navy")}>Contents</span>
      </button>
      <Collapse show={open} durationMs={200}>
        <ul id={listId} className="pb-3">
          {entries.map((entry) => (
            <li key={entry.id}>
              <a
                href={`#${entry.id}`}
                onClick={(event) => {
                  event.preventDefault();
                  go(entry);
                }}
                className={
                  "kind" in entry
                    ? cn(LABEL_CLASS, "flex min-h-10 items-center pt-2 hover:text-navy")
                    : "flex min-h-10 items-center py-1.5 pl-3 text-body text-navy hover:underline hover:underline-offset-[3px]"
                }
              >
                {scrub(entry.title)}
              </a>
            </li>
          ))}
        </ul>
      </Collapse>
    </nav>
  );
}

/**
 * A collapsible artefact section (028 strand 5): real button, aria-expanded,
 * title + one-line summary visible while collapsed. Key findings is NOT
 * collapsible — it always renders in full. The fallback summary carries its
 * marker; a failed summary never renders as a summary.
 *
 * The report while it is written renders its sections through this same
 * component, not collapsible, so the committed report updates them in place
 * (task 058, owner round 7): a section that was showing when it becomes
 * collapsible stays open, and its "Collapse −" control fades in.
 */
export function SectionDisclosure({
  id,
  section,
  defaultOpen,
  collapsible,
  meta,
  summaryNode,
  subhead,
  busy = false,
  arrivingClass = "",
  level = 2,
  children,
}: {
  id: string;
  section: OutlineSection;
  defaultOpen: boolean;
  collapsible: boolean;
  /** Small text after the title in the heading row (a theme's option count). */
  meta?: React.ReactNode;
  /** Shown while collapsed in place of the summary sentence (the option
   *  card's "What it would take" row of cells). */
  summaryNode?: React.ReactNode;
  /** Lines under the heading, before the body (the live page's "Drawing
   *  on" and action lines). */
  subhead?: React.ReactNode;
  /** True while the section is being written (`aria-busy`). */
  busy?: boolean;
  /** A class for controls that arrive with the committed report (the
   *  swap's fade-in), empty otherwise. */
  arrivingClass?: string;
  /** `h3` inside a report part, `h2` on a page without parts (round 10). */
  level?: SectionHeadingLevel;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useRememberedOpen(id, defaultOpen);
  // A section the reader could already read (the live page's, never
  // collapsible) stays open when the committed report makes it collapsible.
  const [wasCollapsible, setWasCollapsible] = useState(collapsible);
  if (wasCollapsible !== collapsible) {
    setWasCollapsible(collapsible);
    if (collapsible) setOpen(true);
  }
  useOpenWhenNavigated(id, setOpen);
  useExpandForPrint(setOpen);
  useExpandAll(setOpen, collapsible);
  const summary = sectionSummary(section);
  const expanded = !collapsible || open;
  const Heading = level === 3 ? "h3" : "h2";
  // The meta moves to its own line as a whole when it does not fit beside
  // the title, and wraps inside itself when it is wider than the column (a
  // list with no themes puts every lever noun on one line; 390 px, task 058).
  const metaSpan = meta !== undefined && (
    <span className="ml-2 inline-block max-w-full text-meta font-normal text-grey max-md:ml-0 max-md:block">{meta}</span>
  );

  return (
    <section
      id={id}
      aria-busy={busy ? true : undefined}
      className={section.role === "conclusions" ? "mb-9 border-t border-line pt-6" : "mb-9"}
    >
      {collapsible ? (
        <DisclosureHeading
          level={level}
          open={expanded}
          onToggle={() => setOpen((value) => !value)}
          wordClassName={arrivingClass}
        >
          {scrub(section.title)}
          {metaSpan}
        </DisclosureHeading>
      ) : (
        <Heading className={REPORT_SECTION_HEADING_CLASS}>
          {scrub(section.title)}
          {metaSpan}
        </Heading>
      )}
      {subhead}
      {/* Fallback (first-sentence) summaries render unmarked — the checked/
          fallback distinction is provenance for reviewers, not users
          (owner, 2026-08-05). */}
      {!expanded && summaryNode !== undefined && <div className="mt-2">{summaryNode}</div>}
      {!expanded && summaryNode === undefined && summary !== null && (
        <p className="mt-1.5 max-w-prose-measure text-lead text-grey max-md:text-body">{scrub(summary.text)}</p>
      )}
      {!expanded && <MobileDisclosureToggle expanded={false} onToggle={() => setOpen(true)} />}
      {expanded && <div className="mt-3 space-y-4">{children}</div>}
      {expanded && collapsible && (
        <MobileDisclosureToggle expanded onToggle={() => setOpen(false)} />
      )}
    </section>
  );
}

/**
 * Mobile-only secondary disclosure toggle (040 D8): the heading row hides its
 * disclosure word below md, so collapsible sections render this tappable
 * twin after the summary (collapsed) or at the section end (expanded), in
 * the same vocabulary (the chevron, "Show" or "Hide"; round 10, C7). The
 * heading row remains a toggle too; this one carries its own aria-expanded.
 */
export function MobileDisclosureToggle({
  expanded,
  onToggle,
}: {
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      aria-expanded={expanded}
      onClick={onToggle}
      className={cn("group print-hide flex min-h-6 cursor-pointer items-center md:hidden", expanded ? "mt-3" : "mt-1.5")}
    >
      <DisclosureWord open={expanded} named />
    </button>
  );
}

/**
 * "How the evidence was gathered" (028 strand 10, fork C hybrid): a
 * collapsible, CITED-scoped section — distributions over only the sources
 * the report cites, with the compact whole-search funnel line and the
 * Landscape pointer for the full corpus. Counts label "Documents".
 */
/** The method section's heading, and its entry in the contents (round 10, C2). */
export const GATHERED_SECTION_TITLE = "How the evidence was gathered";

/**
 * Whether "How the evidence was gathered" renders, from the cited-scope
 * landscape read it is built on: not when the read failed or came back with
 * nothing to show. The contents leave its entry out on the same test
 * (round 10, finding 6). While the read is in flight the section shows.
 */
export function gatheredSectionShows(landscape: {
  isError: boolean;
  data?: { themes?: unknown[] | null; evidence_types?: object | null; years?: object | null; geographies?: object | null } | null;
}): boolean {
  if (landscape.isError) return false;
  const cited = landscape.data;
  if (cited == null) return true;
  return (
    (cited.themes ?? []).length > 0 ||
    Object.keys(cited.evidence_types ?? {}).length > 0 ||
    Object.keys(cited.years ?? {}).length > 0 ||
    Object.keys(cited.geographies ?? {}).length > 0
  );
}

/** The method's tables (owner, round 11): ruled rows at Body, the label
 *  left and the figure right-aligned in one column of tabular figures, every
 *  table one width so the figures line up down the section. */
const GATHERED_TABLE_CLASS = "w-full max-w-[32rem] border-t border-line text-body";
const GATHERED_CAPTION_CLASS = "pb-1.5 text-left font-semibold text-navy";
const GATHERED_ROW_CLASS = "border-b border-line";
const GATHERED_LABEL_CELL_CLASS = "py-1.5 pr-6 text-left align-top font-normal text-ink";
const GATHERED_COUNT_CELL_CLASS = "whitespace-nowrap py-1.5 text-right align-top text-navy";

/**
 * The run's stages from the search to the report, in the Landscape funnel's
 * words (`FUNNEL_STAGES`), each with its count; a stage without one is left
 * out. Five rows: found, relevant (screened in), full text, shortlisted,
 * cited (owner, round 11).
 */
export function gatheredCounts(
  funnel: { found?: number | null; relevant?: number | null; read_in_full?: number | null; selected?: number | null; cited?: number | null } | undefined,
): Array<[label: string, count: number]> {
  if (funnel == null) return [];
  const rows: Array<[string, number | null | undefined]> = [
    ["Found", funnel.found],
    ["Relevant", funnel.relevant],
    [FULL_TEXT, funnel.read_in_full],
    ["Shortlisted", funnel.selected],
    ["Cited", funnel.cited],
  ];
  return rows.filter((row): row is [string, number] => typeof row[1] === "number");
}

/** The geography the landscape counts sources without a country under. */
const NOT_REPORTED_PLACE = "Not reported";

/** Where a count row leads on the sources table, as the Landscape funnel's
 *  rows do: Found to every source, Relevant to the screened-in set, Cited
 *  to the cited sources; Full text and Shortlisted have no filter there. */
export function gatheredCountHref(allSources: string, label: string): string | undefined {
  if (label === "Found") return `${allSources}?status=all`;
  if (label === "Relevant") return `${allSources}?status=Included`;
  if (label === "Cited") return `${allSources}?cited=true`;
  return undefined;
}

/** A row's label: a link in the Link style where the table can filter to
 *  it, plain otherwise (the clickable-only rule). */
function GatheredLabel({ href, children }: { href: string | undefined; children: React.ReactNode }) {
  if (href === undefined) return <>{children}</>;
  return (
    <Link to={href} className={LINK_CLASS}>
      {children}
    </Link>
  );
}

export function GatheredSection({ taskId, id }: { taskId: string; id: string }) {
  const [open, setOpen] = useRememberedOpen(id, false);
  const headingId = useId();
  useOpenWhenNavigated(id, setOpen);
  useExpandForPrint(setOpen);
  useExpandAll(setOpen);
  const landscape = useLandscape(taskId, "cited");
  const funnel = useFunnel(taskId);
  const cited = landscape.data;
  // Each row leads to the sources table where the table can filter to it,
  // with the filters the Landscape's rows use (owner, round 12): the counts
  // to their set, a distribution's value and a theme to the cited sources
  // with that value. A row the table cannot filter to stays plain.
  const allSources = `/tasks/${taskId}/sources/all`;
  const citedWith = (filter: Record<string, string>) =>
    `${allSources}?${new URLSearchParams({ cited: "true", ...filter }).toString()}`;
  const distributions = (() => {
    if (cited === undefined) return [];
    const rows: Array<{ label: string; entries: Array<{ label: string; count: number; href?: string }> }> = [];
    const types = Object.entries(cited.evidence_types ?? {})
      .sort(([, a], [, b]) => b - a)
      .map(([type, count]) => ({ label: evidenceTypeLabel(type), count, href: citedWith({ type }) }));
    if (types.length > 0) rows.push({ label: "Evidence types", entries: types });
    const years = Object.entries(cited.years ?? {})
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([year, count]) => ({ label: year, count, href: citedWith({ year_from: year, year_to: year }) }));
    if (years.length > 0) rows.push({ label: "Publication years", entries: years });
    const places = Object.entries(cited.geographies ?? {})
      .sort(([, a], [, b]) => b - a)
      .map(([country, count]) => ({
        label: country,
        count,
        // "Not reported" is no country the table can filter to.
        href: country === NOT_REPORTED_PLACE ? undefined : citedWith({ country }),
      }));
    if (places.length > 0) rows.push({ label: "Where published", entries: places });
    return rows;
  })();

  const funnelLine =
    funnel.data !== undefined &&
    typeof funnel.data.found === "number" &&
    typeof funnel.data.relevant === "number" &&
    typeof funnel.data.cited === "number"
      ? `${funnel.data.found} found → ${funnel.data.relevant} included → ${funnel.data.cited} cited`
      : null;
  const counts = gatheredCounts(funnel.data);

  if (!gatheredSectionShows(landscape)) return null;

  // The figure alone takes tabular figures: under them some faces widen the
  // space before the word as well.
  const countCell = (count: number) => (
    <>
      <span className="tabular-nums">{count}</span> {count === 1 ? "document" : "documents"}
    </>
  );
  return (
    <section id={id} className="mt-12 border-t border-line pt-6">
      <DisclosureHeading level={2} open={open} onToggle={() => setOpen((value) => !value)}>
        <span id={headingId}>{GATHERED_SECTION_TITLE}</span>
      </DisclosureHeading>
      {/* Shut, the one line under the heading at the References' size. */}
      {!open && funnelLine !== null && (
        <p className="mt-1.5 text-lead text-grey max-md:text-body">{funnelLine}</p>
      )}
      {!open && <MobileDisclosureToggle expanded={false} onToggle={() => setOpen(true)} />}
      {open && (
        <div className="mt-4 space-y-6">
          {/* The search to the report, one stage a row, the numbers in one
              column (owner, round 11); the stages carry the Landscape
              funnel's names. */}
          {counts.length > 0 && (
            <table aria-labelledby={headingId} className={GATHERED_TABLE_CLASS}>
              <tbody>
                {counts.map(([label, count]) => (
                  <tr key={label} className={GATHERED_ROW_CLASS}>
                    <th scope="row" className={GATHERED_LABEL_CELL_CLASS}>
                      <GatheredLabel href={gatheredCountHref(allSources, label)}>{label}</GatheredLabel>
                    </th>
                    <td className={cn(GATHERED_COUNT_CELL_CLASS, "tabular-nums")}>{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="max-w-prose-measure text-body text-grey">
            The rest of this section covers only the cited sources;{" "}
            <Link to={`/tasks/${taskId}/sources/landscape`} className={LINK_CLASS}>
              the Landscape tab
            </Link>{" "}
            shows the whole search.
          </p>
          {distributions.map((row) => (
            <div key={row.label}>
              <table className={GATHERED_TABLE_CLASS}>
                <caption className={GATHERED_CAPTION_CLASS}>{row.label}</caption>
                <tbody>
                  {row.entries.slice(0, 8).map(({ label, count, href }) => (
                    <tr key={label} className={GATHERED_ROW_CLASS}>
                      <th scope="row" className={GATHERED_LABEL_CELL_CLASS}>
                        <GatheredLabel href={href}>{scrub(label)}</GatheredLabel>
                      </th>
                      <td className={cn(GATHERED_COUNT_CELL_CLASS, "text-grey")}>{countCell(count)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {row.label === "Where published" && (
                <p className="mt-2 max-w-prose-measure text-body text-grey">
                  {/* Task 031: the read model reads the publishing venue's country only —
                      never the authors' affiliations, and never where the study was set. */}
                  The country of the publishing venue, when the database reports it — not where
                  each study was set. Sources without one are counted as “Not reported”.
                </p>
              )}
            </div>
          ))}
          {(cited?.themes ?? []).length > 0 && (
            <table className={GATHERED_TABLE_CLASS}>
              <caption className={GATHERED_CAPTION_CLASS}>Key themes</caption>
              <tbody>
                {(cited?.themes ?? []).map((theme) => (
                  <tr key={theme.name} className={GATHERED_ROW_CLASS}>
                    <th scope="row" className={GATHERED_LABEL_CELL_CLASS}>
                      <GatheredLabel href={theme.theme_id != null ? citedWith({ theme: theme.theme_id }) : undefined}>
                        {scrub(theme.name)}
                      </GatheredLabel>
                    </th>
                    {/* The counts at the list's size, one style beside the
                        distributions' (round 10, finding 11). */}
                    <td className={cn(GATHERED_COUNT_CELL_CLASS, "text-grey")}>{countCell(theme.size)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {open && <MobileDisclosureToggle expanded onToggle={() => setOpen(false)} />}
    </section>
  );
}
