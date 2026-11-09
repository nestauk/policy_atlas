import { useState } from "react";
import { Link, useParams } from "react-router";

import { useLandscape, useLonglist, useTask } from "../api/queries";
import type { components } from "../api/gen/types";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { Card } from "../ui/brand/Card";
import { orderThemes } from "../ui/charts/EvidenceDistributionChart";
import { useRunStream, type LiveTheme } from "../store";
import { cn } from "../ui/brand/cn";
import { ReauthRedirect } from "../ui/feedback";
import { ArrivalProvider, useArrives, useFirstPaintDone } from "../ui/motion/arrivals";
import { feedsSources, liveStages, useLiveRefetch } from "./sourcesPresentation";
import { RetryCard } from "../ui/feedback/RetryCard";
import { isScoping } from "./scopingActivity";
import { GroupCount } from "./longlist/GroupHeading";

/** One row of the list: a committed theme, or a discovered one whose count
 *  is on its way (`size` null). */
type ThemeItem = { name: string; size: number | null; description: string; themeId?: string | null };

/**
 * The themes to list (owner, round 9): from the moment the themes are
 * discovered, in the order they were discovered, each with its name and
 * description and its count once the committed landscape has it; the
 * committed themes the discovery did not name follow. Without discovered
 * themes (a reload after the run), the committed themes in their own order.
 *
 * Args:
 *   discovered: The stream's discovered themes, if any.
 *   committed: The landscape's themes, ordered.
 *
 * Returns:
 *   The rows, keyed by name so a count fills in place.
 */
export function themeItems(
  discovered: readonly LiveTheme[] | undefined,
  committed: ReadonlyArray<{ name: string; size: number; description: string; theme_id?: string | null }>,
): ThemeItem[] {
  const byName = new Map(committed.map((theme) => [theme.name, theme]));
  const fromCommitted = (theme: (typeof committed)[number]): ThemeItem => ({
    name: theme.name,
    size: theme.size,
    description: theme.description,
    themeId: theme.theme_id,
  });
  if (discovered === undefined || discovered.length === 0) return committed.map(fromCommitted);
  const named = new Set(discovered.map((theme) => theme.label));
  return [
    ...discovered.map((theme): ThemeItem => {
      const landed = byName.get(theme.label);
      return landed !== undefined
        ? fromCommitted(landed)
        : { name: theme.label, size: null, description: theme.description ?? "" };
    }),
    ...committed.filter((theme) => !named.has(theme.name)).map(fromCommitted),
  ];
}

function documentCount(size: number): string {
  return size === 1 ? "1 document" : `${size} documents`;
}

function ThemeRow({
  name,
  size,
  description,
  to,
  pending,
  arrivalIndex,
}: {
  name: string;
  /** Null while its documents are being assigned: a pulsing bar holds the
   *  count's place, and the count fades in there. */
  size: number | null;
  description: string;
  to?: string;
  /** True while the count is on its way and the stage that fills it runs. */
  pending: boolean;
  /** Its place among themes arriving together (the fade's turn). */
  arrivalIndex: number;
}) {
  // A row that arrives after the page opened fades in, 40 ms after the one
  // before (capped at the sixth); a count that was on its way fades in where
  // its bar was (the animation sweep's entry 7). Opacity only.
  const arrives = useArrives(`theme:${name}`);
  const [waited] = useState(size === null);
  const body = (
    <>
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 text-lead font-bold text-navy">{scrub(name)}</p>
        {size === null ? (
          pending && (
            <span aria-hidden="true" data-testid="theme-count-pulse" className="flex h-[1lh] shrink-0 items-center text-body">
              <span className="placeholder-bar h-2.5 w-20" />
            </span>
          )
        ) : (
          <p key="count" className={cn("shrink-0 text-body text-grey", waited && "anim-swap-in")}>{documentCount(size)}</p>
        )}
      </div>
      {description !== "" && <p className="mt-1 text-body text-grey">{scrub(description)}</p>}
    </>
  );
  return (
    <li
      className={cn("border-b border-line last:border-b-0", arrives && "anim-swap-in")}
      style={arrives ? { animationDelay: `${Math.min(arrivalIndex, 5) * 40}ms` } : undefined}
    >
      {to !== undefined ? (
        <Link
          to={to}
          className="block py-4 no-underline hover:bg-paper-2"
        >
          {body}
        </Link>
      ) : (
        <div className="py-4">{body}</div>
      )}
    </li>
  );
}

/** Placeholder widths per row (the name, then the description), varied so
 *  the rows do not read as a template. */
const PENDING_ROWS = [
  [44, 86],
  [36, 72],
  [52, 64],
] as const;

/**
 * The themes on their way (owner, round 8): while Mapping runs and no theme
 * has landed, three placeholder rows in the themes' own shape (a name, a
 * count at the right, a line of description) breathe on the status mark's
 * 1.6 s rhythm. A screen reader hears when themes appear. Still under
 * reduced motion.
 */
function ThemesPending() {
  return (
    <section>
      <p role="status" className="sr-only">
        Themes appear once the Mapping step has finished.
      </p>
      <ul aria-hidden="true" data-testid="themes-pending">
        {PENDING_ROWS.map(([name, description], index) => (
          <li key={index} className="border-b border-line py-4 last:border-b-0">
            <div className="flex h-[1.5lh] items-center justify-between gap-3 text-lead">
              <span className="placeholder-bar h-3" style={{ width: `${name}%` }} />
              <span className="placeholder-bar h-2.5 w-20 shrink-0" />
            </div>
            <div className="mt-1 flex h-[1lh] items-center text-body">
              <span className="placeholder-bar h-2.5" style={{ width: `${description}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Themes: the reader-facing landscape themes, built only from the existing
 * `landscape.themes` read model — no new text is generated here (rubric 25).
 * Finding-facet groups (intervention, barrier, …) live on the Findings tab.
 */
export function ThemesView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  useDocumentTitle(task.data?.name, "Themes");
  // An options-scoping task's themes are the longlist's option clusters
  // (owner, round 13); an Evidence search's are the landscape's. The
  // longlist is read only on a scoping task.
  const scoping = isScoping(task.data);
  const longlist = useLonglist(scoping ? taskId : "");
  const landscape = useLandscape(taskId);
  // While Mapping runs the themes refetch every 5 s, and until the first
  // lands their rows pulse in place (owner, round 8).
  const stream = useRunStream(taskId);
  const live = liveStages(stream);
  const mapping = live.has("characterise");
  useLiveRefetch(feedsSources(live), () => void landscape.refetch());

  // `not_found` is the server's honest shape for "no landscape yet"
  // (screening hasn't run) — the expected empty state below, not a failure
  // to surface as an error, matching LandscapeView's own treatment.
  const landscapeErrorCode = landscape.isError ? errorCode(landscape.error) : null;
  const isUnauthenticated = landscapeErrorCode === "unauthenticated";
  const isError = landscape.isError && landscapeErrorCode !== "not_found";
  const isPending = landscape.isPending;

  const themes = orderThemes(landscape.data?.themes ?? []);
  // From the moment Mapping has discovered the themes, they show with their
  // names and descriptions while documents are assigned to them, and their
  // counts fill in place (owner, round 9).
  const items = themeItems(stream.liveThemes, themes);
  const isEmpty = !isPending && !isError && items.length === 0;
  const firstPaintDone = useFirstPaintDone(!isPending, taskId);

  if (scoping) return <ScopingThemes taskId={taskId} longlist={longlist} />;

  return (
    <main className="py-8">
      {isPending && (
        <div aria-busy="true" aria-label="Loading themes" className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="anim-breathe h-16 border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {isError &&
        (isUnauthenticated ? (
          <ReauthRedirect />
        ) : (
          <RetryCard copy="Themes couldn't be loaded." onRetry={() => {
                void landscape.refetch();
              }} />
        ))}

      {isEmpty && mapping && <ThemesPending />}

      {isEmpty && !mapping && (
        <Card role="status" className="p-8 text-center text-body text-grey">
          Themes appear once the Mapping step has finished.
        </Card>
      )}

      {items.length > 0 && (
        <ArrivalProvider settled={firstPaintDone} scopeKey={taskId}>
        <section>
          <ul role="list">
            {items.map((theme, index) => (
              <ThemeRow
                key={theme.name}
                name={theme.name}
                size={theme.size}
                description={theme.description}
                pending={mapping}
                arrivalIndex={index}
                to={
                  theme.themeId
                    ? `/tasks/${taskId}/sources/all?theme=${theme.themeId}`
                    : undefined
                }
              />
            ))}
          </ul>
        </section>
        </ArrivalProvider>
      )}
    </main>
  );
}

type LonglistOut = components["schemas"]["LonglistOut"];

/** One option cluster and its options, in the longlist's order. */
export type ScopingTheme = {
  themeId: string;
  name: string;
  description: string;
  options: Array<{ id: string; name: string; excluded: boolean; documents: number }>;
  /** The theme's distinct documents, as the longlist read counts them. */
  documents: number;
};

/**
 * The longlist's themes with their options (owner, round 13): each theme in
 * the longlist's order, its options in the order the theme lists them. An
 * option id the longlist does not carry is left out.
 *
 * Args:
 *   longlist: The longlist read.
 *
 * Returns:
 *   The themes, each with at least one option.
 */
export function scopingThemes(longlist: Pick<LonglistOut, "themes" | "options">): ScopingTheme[] {
  const byId = new Map((longlist.options ?? []).map((option) => [option.option_id, option]));
  return (longlist.themes ?? [])
    .map((theme) => ({
      themeId: theme.theme_id,
      name: theme.name,
      description: theme.description ?? "",
      documents: theme.document_count ?? 0,
      options: (theme.option_ids ?? []).flatMap((id) => {
        const option = byId.get(id);
        return option === undefined
          ? []
          : [{ id, name: option.name, excluded: option.state === "excluded", documents: option.document_count ?? 0 }];
      }),
    }))
    .filter((theme) => theme.options.length > 0);
}

function documentWords(count: number): string {
  return count === 1 ? "1 document" : `${count.toLocaleString("en-GB")} documents`;
}

/**
 * An options-scoping task's Themes subtab (owner, round 13: it was empty
 * after a completed run): the longlist's option clusters from the longlist
 * read, no new endpoint. Each theme is a section: its name at Lead Bold
 * Navy with its option count at the right, its description at Body Grey,
 * then its options as a ruled list, each name a link to its card (an
 * excluded option in Grey, as the longlist sets it).
 */
function ScopingThemes({ taskId, longlist }: { taskId: string; longlist: ReturnType<typeof useLonglist> }) {
  const unauthenticated = longlist.isError && errorCode(longlist.error) === "unauthenticated";
  const themes = longlist.data ? scopingThemes(longlist.data) : [];
  return (
    <main className="py-8">
      {longlist.isPending && (
        <div aria-busy="true" aria-label="Loading themes" className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="anim-breathe h-16 border border-line bg-paper-2" />
          ))}
        </div>
      )}
      {longlist.isError &&
        (unauthenticated ? (
          <ReauthRedirect />
        ) : (
          <RetryCard copy="Themes couldn't be loaded." onRetry={() => void longlist.refetch()} />
        ))}
      {!longlist.isPending && !longlist.isError && themes.length === 0 && (
        <Card role="status" className="p-8 text-center text-body text-grey">
          Themes appear once the longlist is built.
        </Card>
      )}
      {themes.length > 0 && (
        <div className="space-y-10">
          {themes.map((theme) => (
            <ScopingThemeSection key={theme.themeId} taskId={taskId} theme={theme} />
          ))}
        </div>
      )}
    </main>
  );
}

function ScopingThemeSection({ taskId, theme }: { taskId: string; theme: ScopingTheme }) {
  const headingId = `theme-${theme.themeId}`;
  return (
    <section aria-labelledby={headingId}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={headingId} className="min-w-0 text-lead font-bold text-navy">
          {/* The theme opens All sources filtered to it (owner, round 14), in
              the Landscape rows' quiet link form: its own colour, underlined
              on hover. */}
          <Link
            to={`/tasks/${taskId}/sources/all?${new URLSearchParams({ theme: theme.themeId }).toString()}`}
            className="text-inherit no-underline underline-offset-4 hover:underline"
          >
            {scrub(theme.name)}
          </Link>
        </h2>
        {/* Its documents at Meta Grey, as the longlist's group headings carry
            their counts (owner, round 14). */}
        <GroupCount count={documentWords(theme.documents)} className="shrink-0" />
      </div>
      {theme.description !== "" && <p className="mt-1 max-w-[44em] text-body text-grey">{scrub(theme.description)}</p>}
      <ul className="mt-3 border-t border-line">
        {theme.options.map((option) => (
          <li key={option.id} className="border-b border-line">
            <Link
              to={`/tasks/${taskId}/options/${option.id}`}
              className="group flex items-baseline justify-between gap-4 py-3 hover:bg-paper-2"
            >
              <span
                className={cn(
                  "min-w-0 text-body underline-offset-[3px] group-hover:underline",
                  option.excluded ? "text-grey" : "text-navy",
                )}
              >
                {scrub(option.name)}
              </span>
              <GroupCount count={documentWords(option.documents)} className="shrink-0" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
