import { Navigate } from "react-router";

import { usePortfolios, useProjects } from "../api/queries";
import { errorCode } from "../lib/errors";
import { useDocumentTitle } from "../lib/title";
import { TASK } from "../lib/vocabulary";
import { ReauthRedirect } from "../ui/feedback";
import { listPageTitleClass, newTaskHref } from "./listPageChrome";
import { TaskListActions, TaskListPanel } from "./TaskListPanel";

/** Every task, with where it got to and what it belongs to. */
export function TasksListView() {
  useDocumentTitle(TASK.many);
  const projects = useProjects();
  const archived = useProjects({ status: "archived" });
  const portfolios = usePortfolios();

  const rows = projects.data?.data ?? [];
  const portfolioName = new Map(
    (portfolios.data?.data ?? []).map((portfolio) => [portfolio.portfolio_id, portfolio.name]),
  );

  if (projects.isError && errorCode(projects.error) === "unauthenticated") {
    return <ReauthRedirect />;
  }

  const homeIsEmpty =
    !projects.isPending &&
    !archived.isPending &&
    !projects.isError &&
    !archived.isError &&
    (projects.data?.data ?? []).length === 0 &&
    (archived.data?.data ?? []).length === 0;
  if (homeIsEmpty) {
    return <Navigate to="/new" replace />;
  }

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className={listPageTitleClass}>{TASK.many}</h1>
        <TaskListActions
          rows={rows}
          portfolioNames={portfolioName}
          showProjectPrefix
          newTaskHref={newTaskHref()}
        />
      </header>

      <TaskListPanel
        rows={rows}
        portfolioNames={portfolioName}
        showProjectPrefix
        isPending={projects.isPending}
        isError={projects.isError}
        onRetry={() => void projects.refetch()}
        loaded={projects.data !== undefined}
      />
    </main>
  );
}
