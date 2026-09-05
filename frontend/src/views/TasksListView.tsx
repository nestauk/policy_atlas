import { useState } from "react";

import { Navigate } from "react-router";

import { useMe, useProjects, useTasks } from "../api/queries";
import { errorCode } from "../lib/errors";
import { useDocumentTitle } from "../lib/title";
import { TASK, TENANCY_COPY } from "../lib/vocabulary";
import { ReauthRedirect } from "../ui/feedback";
import { showOwnerColumn, listPageTitleClass, newTaskHref } from "./listPageChrome";
import type { Scope } from "./ScopeSwitcher";
import { ScopeSwitcher } from "./ScopeSwitcher";
import { TaskListActions, TaskListPanel } from "./TaskListPanel";

/** Every task, with where it got to and what it belongs to. */
export function TasksListView() {
  useDocumentTitle(TASK.many);
  const me = useMe();
  // Hidden entirely with no organisation (rubric 14's dark-launch invariant,
  // a merge gate): an unenrolled caller's list stays byte-identical to
  // today, including the query itself — no `scope` param is sent.
  const hasSwitcher = me.data?.organisation != null;
  const [scope, setScope] = useState<Scope>("mine");
  const tasks = useTasks(hasSwitcher ? { scope } : undefined);
  const archived = useTasks(
    hasSwitcher ? { scope, status: "archived" } : { status: "archived" },
  );
  const projects = useProjects(hasSwitcher ? { scope } : undefined);

  const rows = tasks.data?.data ?? [];
  const projectName = new Map(
    (projects.data?.data ?? []).map((project) => [project.project_id, project.name]),
  );
  const showOwner = showOwnerColumn(hasSwitcher, rows);
  const isAdminWideList = hasSwitcher && me.data?.is_admin === true && scope === "all";

  if (tasks.isError && errorCode(tasks.error) === "unauthenticated") {
    return <ReauthRedirect />;
  }

  const homeIsEmpty =
    !tasks.isPending &&
    !archived.isPending &&
    !tasks.isError &&
    !archived.isError &&
    (tasks.data?.data ?? []).length === 0 &&
    (archived.data?.data ?? []).length === 0;
  if (homeIsEmpty) {
    return <Navigate to="/new" replace />;
  }

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className={listPageTitleClass}>{TASK.many}</h1>
        {hasSwitcher ? (
          <div className="flex items-center gap-4">
            <ScopeSwitcher scope={scope} onChange={setScope} />
            <TaskListActions
              rows={rows}
              projectNames={projectName}
              showProjectPrefix
              newTaskHref={newTaskHref()}
            />
          </div>
        ) : (
          <TaskListActions
            rows={rows}
            projectNames={projectName}
            showProjectPrefix
            newTaskHref={newTaskHref()}
          />
        )}
      </header>

      {isAdminWideList && (
        <p role="status" className="mb-4 text-meta font-semibold text-grey">
          {TENANCY_COPY.adminWiderList}
        </p>
      )}

      <TaskListPanel
        rows={rows}
        projectNames={projectName}
        showProjectPrefix
        isPending={tasks.isPending}
        isError={tasks.isError}
        onRetry={() => void tasks.refetch()}
        loaded={tasks.data !== undefined}
        showOwner={showOwner}
        ownerlessLabel={isAdminWideList ? TENANCY_COPY.noOrganisation : undefined}
      />
    </main>
  );
}
