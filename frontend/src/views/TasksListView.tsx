import { useState } from "react";

import { Navigate } from "react-router";

import { useMe, useProjects, useTasksPaged } from "../api/queries";
import { errorCode } from "../lib/errors";
import { useDocumentTitle } from "../lib/title";
import { COPY, TASK, TENANCY_COPY } from "../lib/vocabulary";
import { PAGE_COLUMN_CLASS, PageHeader } from "../ui/brand/PageHeader";
import { ReauthRedirect } from "../ui/feedback";
import { showOwnerColumn, newTaskHref } from "./listPageChrome";
import type { ListView } from "./ScopeSwitcher";
import { ScopeSwitcher } from "./ScopeSwitcher";
import { ListEmpty, TaskListActions, TaskListPanel, pagedTasks } from "./TaskListPanel";

type TasksPages = ReturnType<typeof useTasksPaged>;

/** The first page's rows (enough to tell empty from not). */
function firstRows(query: TasksPages) {
  return query.data?.pages[0]?.data ?? [];
}

/** Loaded, and no rows. */
function loadedEmpty(query: TasksPages): boolean {
  return !query.isPending && !query.isError && firstRows(query).length === 0;
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
  // Archived (round 10) lists the reader's own archived tasks, and is
  // offered only while there are some.
  const [chosen, setChosen] = useState<ListView | null>(null);

  // Each scope is asked for once and the open one is shown, so the first-run
  // redirect below can look at every list the caller can open, not only the
  // one on screen. Organisation is asked for only when it is open or Mine is
  // empty, so a caller with tasks of their own sends no extra request.
  const mineQuery = hasSwitcher ? { scope: "mine" as const } : undefined;
  const archivedQuery = hasSwitcher
    ? { scope: "mine" as const, status: "archived" as const }
    : { status: "archived" as const };
  const organisationQuery = hasSwitcher ? { scope: "all" as const } : undefined;
  // Each list is paged by the server (50 a page, `has_more`); "Show more"
  // asks for the next page of the list on screen (round 10).
  const ownTasks = useTasksPaged(mineQuery);
  const ownArchived = useTasksPaged(archivedQuery);
  const ownActiveEmpty = loadedEmpty(ownTasks);
  const ownEmpty = ownActiveEmpty && loadedEmpty(ownArchived);
  const hasArchived = firstRows(ownArchived).length > 0;
  const organisationTasks = useTasksPaged(organisationQuery, {
    enabled: hasSwitcher && (chosen === "all" || ownActiveEmpty),
  });
  const organisationHasRows = firstRows(organisationTasks).length > 0;
  const opening: ListView = hasSwitcher && ownActiveEmpty && organisationHasRows ? "all" : "mine";
  // A choice the list can no longer honour (the last archived task was
  // restored) falls back to where the page opens.
  const view: ListView =
    chosen === null || (chosen === "archived" && !hasArchived) || (chosen === "all" && !hasSwitcher)
      ? opening
      : chosen;
  // Mine is empty and Organisation is still on its way: hold the list's
  // loading frame rather than flash "No tasks yet" before switching.
  const choosingScope =
    hasSwitcher && chosen === null && ownActiveEmpty && organisationTasks.isPending;
  const tasks = view === "all" ? organisationTasks : view === "archived" ? ownArchived : ownTasks;
  const { rows, more } = pagedTasks(tasks);
  const projects = useProjects(hasSwitcher ? { scope: view === "all" ? "all" : "mine" } : undefined);

  const projectName = new Map(
    (projects.data?.data ?? []).map((project) => [project.project_id, project.name]),
  );
  const showOwner = showOwnerColumn(hasSwitcher, rows, view);
  const isAdminWideList = hasSwitcher && me.data?.is_admin === true && view === "all";

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
        filters={
          hasSwitcher || hasArchived ? (
            <ScopeSwitcher
              scope={view}
              onChange={setChosen}
              showOrganisation={hasSwitcher}
              showArchived={hasArchived}
            />
          ) : null
        }
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
          // A page after the first that fails keeps the rows and offers
          // Retry at the foot; only a failed first page replaces the list.
          isError={tasks.isError && !tasks.isFetchNextPageError}
          onRetry={() => void tasks.refetch()}
          loaded={tasks.data !== undefined}
          showOwner={showOwner}
          ownerlessLabel={isAdminWideList ? TENANCY_COPY.noOrganisation : undefined}
          more={more}
          empty={
            <ListEmpty label={COPY.noTasks}>{TASK.many} you start appear here.</ListEmpty>
          }
        />
      </div>
    </main>
  );
}
