import { useState } from "react";

import { Navigate } from "react-router";

import { useMe, useProjects, useTasksPaged } from "../api/queries";
import { errorCode } from "../lib/errors";
import { useDocumentTitle } from "../lib/title";
import { COPY, TASK, TENANCY_COPY } from "../lib/vocabulary";
import { PAGE_COLUMN_CLASS, PageHeader, PagePrimary } from "../ui/brand/PageHeader";
import { ReauthRedirect } from "../ui/feedback";
import { showOwnerColumn, newTaskHref } from "./listPageChrome";
import type { Scope } from "./ScopeSwitcher";
import { ARCHIVED_HEADING_CLASS, ArchivedToggle, ScopeSwitcher } from "./ScopeSwitcher";
import { FindTasks, ListEmpty, TaskListPanel, pagedTasks } from "./TaskListPanel";

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
  const [chosen, setChosen] = useState<Scope | null>(null);
  // Archived is not a scope (owner, round 11): a toggle that lists the
  // archived tasks of the open scope, the reader's on Mine, the
  // organisation's on Organisation. The scope is kept across it.
  const [archived, setArchived] = useState(false);

  // Each scope is asked for once and the open one is shown, so the first-run
  // redirect below can look at every list the caller can open, not only the
  // one on screen. Organisation is asked for only when it is open or Mine is
  // empty, so a caller with tasks of their own sends no extra request.
  const mineQuery = hasSwitcher ? { scope: "mine" as const } : undefined;
  const archivedQuery = hasSwitcher
    ? { scope: "mine" as const, status: "archived" as const }
    : { status: "archived" as const };
  const organisationQuery = hasSwitcher ? { scope: "all" as const } : undefined;
  const organisationArchivedQuery = hasSwitcher
    ? { scope: "all" as const, status: "archived" as const }
    : undefined;
  // Each list is paged by the server (50 a page, `has_more`); "Show more"
  // asks for the next page of the list on screen (round 10).
  const ownTasks = useTasksPaged(mineQuery);
  // The reader's archive is always asked for: the first-run redirect below
  // must not send a reader whose tasks are all archived to /new.
  const ownArchived = useTasksPaged(archivedQuery);
  const ownActiveEmpty = loadedEmpty(ownTasks);
  const ownEmpty = ownActiveEmpty && loadedEmpty(ownArchived);
  const organisationTasks = useTasksPaged(organisationQuery, {
    enabled: hasSwitcher && (chosen === "all" || ownActiveEmpty),
  });
  const organisationHasRows = firstRows(organisationTasks).length > 0;
  const opening: Scope = hasSwitcher && ownActiveEmpty && organisationHasRows ? "all" : "mine";
  const scope: Scope = chosen === null || (chosen === "all" && !hasSwitcher) ? opening : chosen;
  // The organisation's archive is asked for only once it is open.
  const organisationArchived = useTasksPaged(organisationArchivedQuery, {
    enabled: hasSwitcher && scope === "all" && archived,
  });
  // Mine is empty and Organisation is still on its way: hold the list's
  // loading frame rather than flash "No tasks yet" before switching.
  const choosingScope =
    hasSwitcher && chosen === null && ownActiveEmpty && organisationTasks.isPending;
  const tasks =
    scope === "all"
      ? archived
        ? organisationArchived
        : organisationTasks
      : archived
        ? ownArchived
        : ownTasks;
  const { rows, more } = pagedTasks(tasks);
  const projects = useProjects(hasSwitcher ? { scope } : undefined);

  const projectName = new Map(
    (projects.data?.data ?? []).map((project) => [project.project_id, project.name]),
  );
  const showOwner = showOwnerColumn(hasSwitcher, rows, scope);
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
        // The header keeps only the primary (owner, round 11).
        actions={<PagePrimary to={newTaskHref()}>{COPY.newTask}</PagePrimary>}
        filters={hasSwitcher ? <ScopeSwitcher scope={scope} onChange={setChosen} /> : null}
        // The row's right end: the admin's note, then the magnifier
        // (owner, round 11). The magnifier's 40 px box carries 12 px of air
        // each side of its glyph, so an 8 px gap reads as 20 px, and -mr-3
        // sets the glyph on the column's edge, under the primary's.
        aside={
          <div className="flex flex-wrap items-center justify-end gap-x-2 gap-y-2">
            {isAdminWideList && (
              <p role="status" className="text-meta font-semibold text-grey">
                {TENANCY_COPY.adminWiderList}
              </p>
            )}
            <FindTasks rows={rows} projectNames={projectName} showProjectPrefix className="-mr-3" />
          </div>
        }
      />

      <div className="mt-4">
        {/* With the archive open, the list says what it is (owner, round 11). */}
        {archived && <h2 className={ARCHIVED_HEADING_CLASS}>Archived</h2>}
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
          footEnd={<ArchivedToggle pressed={archived} onToggle={() => setArchived((on) => !on)} />}
          empty={
            archived ? (
              <ListEmpty label={`No archived ${TASK.lowerMany}`} />
            ) : (
              <ListEmpty label={COPY.noTasks}>{TASK.many} you start appear here.</ListEmpty>
            )
          }
        />
      </div>
    </main>
  );
}
