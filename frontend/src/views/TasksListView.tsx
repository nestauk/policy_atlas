import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { usePortfolios, useProjects } from "../api/queries";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { COPY, PROJECT, TASK } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Card, StatusDot } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { taskStatus } from "./landingPresentation";
import { taskDestination } from "./lifecycle";

type ProjectRow = {
  project_id: string;
  name: string;
  updated_at: string;
  latest_run?: { status: string; ended_at?: string | null } | null;
  portfolio_id?: string | null;
  source_count?: number | null;
};

/**
 * Find a task by name.
 *
 * Filtering happens over the loaded list rather than server-side: the list is
 * one page of the caller's own tasks, so a round trip per keystroke would buy
 * nothing. If the list ever outgrows a page this becomes a real query.
 */
function FindTask({
  rows,
  onClose,
}: {
  rows: readonly ProjectRow[];
  onClose: () => void;
}) {
  const [term, setTerm] = useState("");
  const navigate = useNavigate();
  const needle = term.trim().toLowerCase();
  const matches =
    needle === "" ? rows : rows.filter((row) => row.name.toLowerCase().includes(needle));

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={COPY.findTask}
      className="fixed inset-x-0 top-24 z-30 mx-auto max-w-xl border border-line bg-paper p-4 shadow-lg"
    >
      <div className="flex items-center gap-3">
        <label className="sr-only" htmlFor="find-task">
          {COPY.findTask}
        </label>
        <input
          id="find-task"
          autoFocus
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") onClose();
          }}
          placeholder={`Search ${TASK.lowerMany} by name`}
          className="flex-1 border border-line-2 bg-paper px-3 py-2 text-body text-navy focus-visible:outline-2 focus-visible:outline-blue"
        />
        <button
          type="button"
          aria-label="Close search"
          onClick={onClose}
          className="cursor-pointer text-heading leading-none text-grey hover:text-navy"
        >
          ×
        </button>
      </div>
      <ul role="list" className="mt-3 max-h-80 overflow-y-auto">
        {matches.length === 0 && (
          <li className="px-1 py-3 text-body text-grey">Nothing matches “{scrub(term)}”.</li>
        )}
        {matches.map((row) => (
          <li key={row.project_id}>
            <button
              type="button"
              onClick={() => {
                onClose();
                // Opens where the task actually is, not a generic page.
                void navigate(taskDestination(row.project_id, row.latest_run?.status as never));
              }}
              className="w-full cursor-pointer border-b border-line px-1 py-2.5 text-left text-body text-navy last:border-b-0 hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-blue"
            >
              {scrub(row.name)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Every task, with where it got to and what it belongs to. */
export function TasksListView() {
  useDocumentTitle(TASK.many);
  const projects = useProjects();
  const portfolios = usePortfolios();
  const [finding, setFinding] = useState(false);

  const rows = (projects.data?.data ?? []) as ProjectRow[];
  const portfolioName = new Map(
    (portfolios.data?.data ?? []).map((portfolio) => [portfolio.portfolio_id, portfolio.name]),
  );

  if (projects.isError && errorCode(projects.error) === "unauthenticated") {
    return <ReauthRedirect />;
  }

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className="font-display text-title font-extrabold tracking-[-0.5px] text-navy">
          {TASK.many}
        </h1>
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={() => setFinding(true)}>
            {COPY.findTask}
          </Button>
          <Link to="/portfolios" className="text-meta font-semibold text-grey hover:text-navy">
            {PROJECT.many}
          </Link>
          <Link
            to="/new"
            className="cutout bg-blue px-3 py-2 text-meta font-bold text-white no-underline"
          >
            {COPY.newTask}
          </Link>
        </div>
      </header>

      {finding && <FindTask rows={rows} onClose={() => setFinding(false)} />}

      {projects.isPending && (
        <div aria-busy="true" aria-label={`Loading ${TASK.lowerMany}`} className="space-y-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="h-14 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {projects.isError && (
        <Card role="alert" className="max-w-md p-5 text-body text-navy">
          Your {TASK.lowerMany} couldn't be loaded.{" "}
          <button
            type="button"
            className="cursor-pointer font-bold text-blue hover:underline"
            onClick={() => void projects.refetch()}
          >
            Retry
          </button>
        </Card>
      )}

      {projects.data !== undefined && rows.length === 0 && (
        <Card role="status" className="mx-auto max-w-md p-8 text-center">
          <h2 className="font-display text-heading font-bold text-navy">{COPY.noTasks}</h2>
          <p className="mt-1.5 text-body text-grey">
            Start with the policy question you need evidence for.
          </p>
          <Link
            to="/new"
            className="cutout mt-4 inline-block bg-blue px-3 py-2 text-meta font-bold text-white no-underline"
          >
            {COPY.newTask}
          </Link>
        </Card>
      )}

      {rows.length > 0 && (
        <ul role="list" className="border border-line-2 bg-paper">
          {rows.map((row) => {
            const status = taskStatus(row.latest_run as never);
            return (
              <li key={row.project_id} className="border-b border-line last:border-b-0">
                <Link
                  to={taskDestination(row.project_id, row.latest_run?.status as never)}
                  className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3.5 no-underline hover:bg-blue-tint-2"
                >
                  <span className="min-w-0 flex-1 text-body font-semibold text-navy">
                    {scrub(row.name)}
                  </span>
                  {row.portfolio_id != null && (
                    <Chip tone="soft">{scrub(portfolioName.get(row.portfolio_id) ?? PROJECT.one)}</Chip>
                  )}
                  {/* null and 0 differ: null means no run has asked yet. */}
                  {row.source_count != null && (
                    <span className="text-meta text-grey">
                      {row.source_count === 1 ? "1 source" : `${row.source_count} sources`}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1.5 text-meta text-grey">
                    <StatusDot tone={status.dot} />
                    {status.label}
                  </span>
                  <time
                    dateTime={row.updated_at}
                    className="w-28 shrink-0 text-right text-meta tabular-nums text-grey"
                  >
                    {new Date(row.updated_at).toLocaleDateString()}
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
