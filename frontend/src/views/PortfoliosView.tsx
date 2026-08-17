import { useState } from "react";
import { Link, useParams } from "react-router";

import { usePortfolio, usePortfolios, useProjects } from "../api/queries";
import { useCreatePortfolio } from "../api/mutations";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { COPY, PROJECT, TASK } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Card, StatusDot } from "../ui/brand/Card";
import { taskStatus } from "./landingPresentation";
import { taskDestination } from "./lifecycle";

/**
 * Projects: named groupings of tasks, and nothing else.
 *
 * A project holds no plan, no run and no evidence of its own, so the page
 * shows a name and a count and stops there. Anything more would imply the
 * grouping has a state, which it does not.
 */
export function PortfoliosView() {
  useDocumentTitle(PROJECT.many);
  const portfolios = usePortfolios();
  const create = useCreatePortfolio();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className="font-display text-title font-extrabold tracking-[-0.5px] text-navy">
          {PROJECT.many}
        </h1>
        <div className="flex items-center gap-3">
          <Link to="/" className="text-meta font-semibold text-grey hover:text-navy">
            {COPY.allTasks}
          </Link>
          {!creating && <Button onClick={() => setCreating(true)}>New {PROJECT.lower}</Button>}
        </div>
      </header>

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
          <h2 className="font-display text-heading font-bold text-navy">
            No {PROJECT.lowerMany} yet
          </h2>
          <p className="mt-1.5 text-body text-grey">
            A {PROJECT.lower} groups related {TASK.lowerMany} under one name.
          </p>
        </Card>
      )}

      {(portfolios.data?.data.length ?? 0) > 0 && (
        <ul role="list" className="border border-line-2 bg-paper">
          {portfolios.data?.data.map((portfolio) => (
            <li key={portfolio.portfolio_id} className="border-b border-line last:border-b-0">
              <Link
                to={`/portfolios/${portfolio.portfolio_id}`}
                className="flex items-baseline justify-between gap-4 px-4 py-3.5 no-underline hover:bg-blue-tint-2"
              >
                <span className="min-w-0 flex-1 text-body font-semibold text-navy">
                  {scrub(portfolio.name)}
                </span>
                <span className="text-meta text-grey">
                  {portfolio.task_count === 1
                    ? `1 ${TASK.lower}`
                    : `${portfolio.task_count} ${TASK.lowerMany}`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

/** One project: its name, and the tasks in it. Nothing else. */
export function PortfolioDetailView() {
  const { portfolioId = "" } = useParams();
  const portfolio = usePortfolio(portfolioId);
  const projects = useProjects();
  useDocumentTitle(portfolio.data?.name, PROJECT.one);

  const tasks = (projects.data?.data ?? []).filter(
    (project) => project.portfolio_id === portfolioId,
  );

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <Link to="/portfolios" className="text-meta font-semibold text-grey hover:text-navy">
        ← {PROJECT.many}
      </Link>
      <h1 className="mt-2 font-display text-title font-extrabold tracking-[-0.5px] text-navy">
        {portfolio.data === undefined ? "" : scrub(portfolio.data.name)}
      </h1>
      {portfolio.data?.description != null && (
        <p className="mt-2 max-w-prose text-body text-grey">{scrub(portfolio.data.description)}</p>
      )}

      {tasks.length === 0 && (
        <Card role="status" className="mt-8 max-w-md p-8 text-center text-body text-grey">
          No {TASK.lowerMany} in this {PROJECT.lower} yet.
        </Card>
      )}

      {tasks.length > 0 && (
        <ul role="list" className="mt-6 border border-line-2 bg-paper">
          {tasks.map((task) => {
            const status = taskStatus(task.latest_run);
            return (
              <li key={task.project_id} className="border-b border-line last:border-b-0">
                <Link
                  to={taskDestination(task.project_id, task.latest_run?.status)}
                  className="flex items-baseline justify-between gap-4 px-4 py-3.5 no-underline hover:bg-blue-tint-2"
                >
                  <span className="min-w-0 flex-1 text-body font-semibold text-navy">
                    {scrub(task.name)}
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-meta text-grey">
                    <StatusDot tone={status.dot} />
                    {status.label}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
