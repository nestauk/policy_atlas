import { useProjects, useTasks } from "../api/queries";
import { errorCode } from "../lib/errors";
import { useDocumentTitle } from "../lib/title";
import { TASK } from "../lib/vocabulary";
import { ReauthRedirect } from "../ui/feedback";
import { listPageTitleClass, newTaskHref } from "./listPageChrome";
import { TaskListActions, TaskListPanel } from "./TaskListPanel";

/** Every task, with where it got to and what it belongs to. */
export function TasksListView() {
  useDocumentTitle(TASK.many);
  const tasks = useTasks();
  const projects = useProjects();

  const rows = tasks.data?.data ?? [];
  const projectName = new Map(
    (projects.data?.data ?? []).map((project) => [project.project_id, project.name]),
  );

  if (tasks.isError && errorCode(tasks.error) === "unauthenticated") {
    return <ReauthRedirect />;
  }

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className={listPageTitleClass}>{TASK.many}</h1>
        <TaskListActions
          rows={rows}
          projectNames={projectName}
          showTaskPrefix
          newTaskHref={newTaskHref()}
        />
      </header>

      <TaskListPanel
        rows={rows}
        projectNames={projectName}
        showTaskPrefix
        isPending={tasks.isPending}
        isError={tasks.isError}
        onRetry={() => void tasks.refetch()}
        loaded={tasks.data !== undefined}
      />
    </main>
  );
}
