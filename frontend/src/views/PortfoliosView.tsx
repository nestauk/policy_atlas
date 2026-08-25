import { useState } from "react";
import { Link, useParams } from "react-router";

import { useMe, usePortfolio, usePortfolios, useProjects } from "../api/queries";
import { useCreatePortfolio, useUpdatePortfolio } from "../api/mutations";
import { isConflictCode, conflictSentences } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { PROJECT, TASK, TENANCY_COPY } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";
import { useToast } from "../ui/radix/Toast";
import {
  listPageTitleClass,
  listSecondaryActionClass,
  newTaskHref,
  newestTaskUpdateByPortfolio,
  portfolioLastUpdated,
  showOwnerColumn,
  sortPortfoliosByLastUpdated,
} from "./listPageChrome";
import type { Scope } from "./ScopeSwitcher";
import { ScopeSwitcher } from "./ScopeSwitcher";
import { TaskListActions, TaskListPanel } from "./TaskListPanel";
import { VisibilityControl, visibilityOutcomeLine } from "./VisibilityControl";

/**
 * Projects: named groupings of tasks, and nothing else.
 *
 * A project holds no plan, no run and no evidence of its own, so the page
 * shows a name and a count and stops there. Anything more would imply the
 * grouping has a state, which it does not.
 */
/** `PortfolioOut` carries a derived `task_count` but no last-task-updated
 *  timestamp, so this overview still leans on the global projects page to
 *  derive "most recently active" per portfolio (`newestTaskUpdateByPortfolio`
 *  below) — asking per-portfolio would be N+1 requests for a list page.
 *  Server page-size cap (`PAGE_SIZE_MAX`, web-api.md § Pagination): raised
 *  from the 50-row default so this remains an approximation rather than
 *  systematically wrong, not a fix — a workspace with more than 200 active
 *  projects across portfolios can still miss a newer update that falls
 *  outside this page. `PortfolioDetailView` does not share this limitation:
 *  it fetches its own member list via `portfolio_id`, which is exact
 *  regardless of this page size (task 033 phase 10a). */
const PORTFOLIOS_OVERVIEW_PROJECTS_PAGE_SIZE = 200;

export function PortfoliosView() {
  useDocumentTitle(PROJECT.many);
  const me = useMe();
  // Hidden entirely with no organisation (rubric 14's dark-launch invariant):
  // an unenrolled caller's page — including its queries — stays unchanged.
  const hasSwitcher = me.data?.organisation != null;
  const [scope, setScope] = useState<Scope>("all");
  const portfolios = usePortfolios(hasSwitcher ? { scope } : undefined);
  const projects = useProjects(
    hasSwitcher
      ? { page_size: PORTFOLIOS_OVERVIEW_PROJECTS_PAGE_SIZE, scope }
      : { page_size: PORTFOLIOS_OVERVIEW_PROJECTS_PAGE_SIZE },
  );
  const create = useCreatePortfolio();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const taskUpdatedAt = newestTaskUpdateByPortfolio(projects.data?.data ?? []);
  const rows = sortPortfoliosByLastUpdated(portfolios.data?.data ?? [], taskUpdatedAt);
  const showOwner = showOwnerColumn(hasSwitcher, rows);
  const isAdminWideList = hasSwitcher && me.data?.is_admin === true && scope === "all";
  const ownerlessLabel = isAdminWideList ? TENANCY_COPY.noOrganisation : TENANCY_COPY.ownerlessRow;

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className={listPageTitleClass}>{PROJECT.many}</h1>
        <div className="flex items-center gap-4">
          {hasSwitcher && <ScopeSwitcher scope={scope} onChange={setScope} />}
          {!creating && (
            <Button className="px-6 py-3.5 text-body" onClick={() => setCreating(true)}>
              New {PROJECT.lower}
            </Button>
          )}
        </div>
      </header>

      {isAdminWideList && (
        <p role="status" className="mb-4 text-meta font-semibold text-grey">
          {TENANCY_COPY.adminWiderList}
        </p>
      )}

      {creating && (
        <Card className="mb-8 max-w-md p-5">
          <form
            className="flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              const trimmed = name.trim();
              if (!trimmed) return;
              create.mutate(
                { name: trimmed },
                {
                  onSuccess: () => {
                    setName("");
                    setCreating(false);
                  },
                },
              );
            }}
          >
            <label className="text-meta font-semibold text-navy" htmlFor="new-portfolio-name">
              {PROJECT.one} name
            </label>
            <input
              id="new-portfolio-name"
              autoFocus
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="border border-line-2 bg-paper px-3 py-2.5 text-body focus-visible:outline-2 focus-visible:outline-blue"
            />
            {create.isError && (
              <p role="alert" className="text-body text-red">
                The {PROJECT.lower} couldn't be created. Try again.
              </p>
            )}
            <div className="flex items-center gap-2">
              <Button type="submit" disabled={create.isPending || !name.trim()}>
                Create
              </Button>
              <Button type="button" variant="ghost" onClick={() => setCreating(false)}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      {portfolios.isPending && (
        <div aria-busy="true" aria-label={`Loading ${PROJECT.lowerMany}`} className="space-y-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-14 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {portfolios.data !== undefined && portfolios.data.data.length === 0 && !creating && (
        <Card role="status" className="mx-auto max-w-md p-8 text-center">
          <h2 className="text-heading font-extrabold text-navy">No {PROJECT.lowerMany} yet</h2>
          <p className="mt-1.5 text-body text-grey">
            A {PROJECT.lower} groups related {TASK.lowerMany} under one name.
          </p>
        </Card>
      )}

      {(portfolios.data?.data.length ?? 0) > 0 && (
        <ul role="list" className="border border-line-2 bg-paper">
          {rows.map((portfolio) => {
            const lastUpdated = portfolioLastUpdated(portfolio, taskUpdatedAt);
            return (
              <li key={portfolio.portfolio_id} className="border-b border-line last:border-b-0">
                <Link
                  to={`/portfolios/${portfolio.portfolio_id}`}
                  className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3.5 no-underline hover:bg-blue-tint-2"
                >
                  <span className="min-w-0 flex-1 text-body font-semibold text-navy">
                    {scrub(portfolio.name)}
                  </span>
                  {showOwner && (
                    <span className="text-meta text-grey">
                      {portfolio.owner_display !== null ? scrub(portfolio.owner_display) : ownerlessLabel}
                    </span>
                  )}
                  <span className="text-meta text-grey">
                    {portfolio.task_count === 1
                      ? `1 ${TASK.lower}`
                      : `${portfolio.task_count} ${TASK.lowerMany}`}
                  </span>
                  <time
                    dateTime={lastUpdated}
                    className="w-28 shrink-0 text-right text-caption tabular-nums text-grey"
                  >
                    {new Date(lastUpdated).toLocaleDateString()}
                  </time>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}

/** One project: its tasks, with the same list chrome as the Tasks page. */
export function PortfolioDetailView() {
  const { portfolioId = "" } = useParams();
  const me = useMe();
  const portfolio = usePortfolio(portfolioId);
  // Server-side `portfolio_id` filter (task 033 phase 10a) — this used to
  // filter the global 50-row projects page client-side, silently
  // under-reporting once a portfolio's membership (or the caller's visible
  // estate) grew past that page.
  const projects = useProjects({ portfolio_id: portfolioId });
  const updatePortfolio = useUpdatePortfolio(portfolioId);
  const toast = useToast();
  useDocumentTitle(portfolio.data?.name, PROJECT.one);

  const tasks = projects.data?.data ?? [];
  const hasSwitcher = me.data?.organisation != null;
  const showOwner = showOwnerColumn(hasSwitcher, tasks);
  const isAdminWideList = hasSwitcher && me.data?.is_admin === true;
  const ownerlessLabel = isAdminWideList ? TENANCY_COPY.noOrganisation : TENANCY_COPY.ownerlessRow;

  const changeVisibility = (next: "org" | "private") => {
    updatePortfolio.mutate(
      { visibility: next },
      {
        onSuccess: (updated) => {
          toast.toast({ title: visibilityOutcomeLine(next, updated.task_count), tone: "default" });
        },
        onError: (error) => {
          const code = (error as { code?: string }).code;
          const message = isConflictCode(code)
            ? conflictSentences[code]
            : `The ${PROJECT.lower} couldn't be updated. Try again.`;
          toast.toast({ title: message, tone: "error" });
        },
      },
    );
  };

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <Link to="/portfolios" className={listSecondaryActionClass}>
            ← {PROJECT.many}
          </Link>
          <h1 className={`${listPageTitleClass} mt-2`}>
            {portfolio.data === undefined ? "" : scrub(portfolio.data.name)}
          </h1>
          {portfolio.data?.description != null && (
            <p className="mt-2 max-w-prose text-body text-grey">
              {scrub(portfolio.data.description)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-4">
          {portfolio.data !== undefined && (
            <VisibilityControl
              visibility={portfolio.data.visibility}
              isOwner={portfolio.data.is_owner}
              pending={updatePortfolio.isPending}
              onChange={changeVisibility}
            />
          )}
          <TaskListActions rows={tasks} newTaskHref={newTaskHref(portfolioId)} />
        </div>
      </header>

      <TaskListPanel
        rows={tasks}
        isPending={portfolio.isPending || projects.isPending}
        isError={portfolio.isError || projects.isError}
        onRetry={() => {
          void portfolio.refetch();
          void projects.refetch();
        }}
        loaded={portfolio.data !== undefined && projects.data !== undefined}
        showOwner={showOwner}
        ownerlessLabel={ownerlessLabel}
      />
    </main>
  );
}
