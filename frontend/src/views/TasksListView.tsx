import { useState } from "react";

import { Navigate } from "react-router";

import { useMe, useProjects, useTasks } from "../api/queries";
import { errorCode } from "../lib/errors";
import { useDocumentTitle } from "../lib/title";
import { COPY, TASK, TENANCY_COPY } from "../lib/vocabulary";
import { PAGE_COLUMN_CLASS, PageHeader } from "../ui/brand/PageHeader";
import { ReauthRedirect } from "../ui/feedback";
import { showOwnerColumn, newTaskHref } from "./listPageChrome";
import type { Scope } from "./ScopeSwitcher";
import { ScopeSwitcher } from "./ScopeSwitcher";
import { ListEmpty, TaskListActions, TaskListPanel } from "./TaskListPanel";

type TasksPage = ReturnType<typeof useTasks>;

/** Loaded, and no rows. */
function loadedEmpty(query: TasksPage): boolean {
  return !query.isPending && !query.isError && (query.data?.data ?? []).length === 0;
}

/** Every task, with where it got to and what it belongs to. */
export function TasksListView() {
  useDocumentTitle(TASK.many);
  const me = useMe();
  // Hidden entirely with no organisation (rubric 14's dark-launch invariant,
  // a merge gate): an unenrolled caller's list stays byte-identical to
  // today, including the query itself — no `scope` param is sent.
  const hasSwitcher = me.data?.organisation != null;
  // `chosen` is the caller's own pick; until they pick, the page opens on
  // Mine, or on Organisation when Mine is empty and colleagues have tasks
  // (lead ruling, 2026-11-05: the owner's point was that colleagues' tasks
  // were unreachable from an empty Mine).
  const [chosen, setChosen] = useState<Scope | null>(null);

  // Each scope is asked for once and the open one is shown, so the first-run
  // redirect below can look at every list the caller can open, not only the
  // one on screen. Organisation is asked for only when it is open or Mine is
  // empty, so a caller with tasks of their own sends no extra request.
  const ownTasks = useTasks(hasSwitcher ? { scope: "mine" } : undefined);
  const ownArchived = useTasks(
    hasSwitcher ? { scope: "mine", status: "archived" } : { status: "archived" },
  );
  const ownActiveEmpty = loadedEmpty(ownTasks);
  const ownEmpty = ownActiveEmpty && loadedEmpty(ownArchived);
  const organisationTasks = useTasks(hasSwitcher ? { scope: "all" } : undefined, {
    enabled: hasSwitcher && (chosen === "all" || ownActiveEmpty),
  });
  const organisationHasRows = (organisationTasks.data?.data ?? []).length > 0;
  const scope: Scope =
    chosen ?? (hasSwitcher && ownActiveEmpty && organisationHasRows ? "all" : "mine");
  // Mine is empty and Organisation is still on its way: hold the list's
  // loading frame rather than flash "No tasks yet" before switching.
  const choosingScope =
    hasSwitcher && chosen === null && ownActiveEmpty && organisationTasks.isPending;
  const tasks = scope === "all" ? organisationTasks : ownTasks;
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

  // Wait for /me: until it lands an enrolled caller looks unenrolled, and
  // their empty Mine list would redirect before Organisation was asked.
  const meKnown = me.data !== undefined || me.isError === true;
  const homeIsEmpty =
    meKnown && ownEmpty && (!hasSwitcher || loadedEmpty(organisationTasks));
  if (homeIsEmpty) {
    return <Navigate to="/new" replace />;
  }

  return (
    <main className={PAGE_COLUMN_CLASS}>
      <PageHeader
        title={TASK.many}
        actions={
          <TaskListActions
            rows={rows}
            projectNames={projectName}
            showProjectPrefix
            newTaskHref={newTaskHref()}
          />
        }
        filters={hasSwitcher ? <ScopeSwitcher scope={scope} onChange={setChosen} /> : null}
        aside={
          isAdminWideList ? (
            <p role="status" className="text-meta font-semibold text-grey">
              {TENANCY_COPY.adminWiderList}
            </p>
          ) : null
        }
      />

      <div className="mt-4">
        <TaskListPanel
          rows={rows}
          projectNames={projectName}
          showProjectPrefix
          isPending={tasks.isPending || choosingScope}
          isError={tasks.isError}
          onRetry={() => void tasks.refetch()}
          loaded={tasks.data !== undefined}
          showOwner={showOwner}
          ownerlessLabel={isAdminWideList ? TENANCY_COPY.noOrganisation : undefined}
          empty={
            <ListEmpty label={COPY.noTasks}>{TASK.many} you start appear here.</ListEmpty>
          }
        />
      </div>
    </main>
  );
}
