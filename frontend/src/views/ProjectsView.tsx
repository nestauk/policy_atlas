import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";

import type { components } from "../api/gen/types";
import {
  queryKeys,
  useMe,
  useProject,
  useProjectsPaged,
  useTasksPaged,
} from "../api/queries";
import { useArchiveProject, useCreateProject, useUpdateProject } from "../api/mutations";
import { isConflictCode, conflictSentences } from "../lib/errors";
import { Figures } from "../lib/figures";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { COPY, PROJECT, TASK, TENANCY_COPY } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";
import {
  PAGE_COLUMN_CLASS,
  PAGE_CONTROL_CLASS,
  PageBackLink,
  PageHeader,
  PagePrimary,
} from "../ui/brand/PageHeader";
import { useToast } from "../ui/radix/Toast";
import {
  formatListDate,
  listFrameClass,
  newTaskHref,
  projectListRowGridClass,
  projectListRowGridClassWithOwner,
  rowFigureCellClass,
  rowAccessibleName,
  rowNameCellClass,
  rowOwnerCellClass,
  showOwnerColumn,
} from "./listPageChrome";
import type { Scope } from "./ScopeSwitcher";
import { ARCHIVED_HEADING_CLASS, ArchivedToggle, ScopeSwitcher } from "./ScopeSwitcher";
import {
  ListEmpty,
  ListError,
  FindTasks,
  ListFootRow,
  ListSkeleton,
  ShowMore,
  TaskListPanel,
  pagedTasks,
  type MoreTasks,
} from "./TaskListPanel";
import { FindPopover } from "./FindPopover";
import { RowFold, RowMenuControl, RowRenameField, useDepartingRows } from "./ListRowMenu";
import { ProjectName } from "./NameMenu";
import { VisibilityControl, visibilityOutcomeLine } from "./VisibilityControl";

/**
 * Projects: named groupings of tasks, and nothing else.
 *
 * A task holds no plan, no run and no evidence of its own, so the page
 * shows a name and a count and stops there. Anything more would imply the
 * grouping has a state, which it does not.
 */
/** A project's own task list asks for the server's largest page (200,
 *  `PAGE_SIZE_MAX`, web-api.md § Pagination) rather than the default, with
 *  "Show more" past it (round 10). */
const PROJECT_TASKS_PAGE_SIZE = 200;

export function ProjectsView() {
  useDocumentTitle(PROJECT.many);
  const me = useMe();
  // Hidden entirely with no organisation (rubric 14's dark-launch invariant):
  // an unenrolled caller's page — including its queries — stays unchanged.
  const hasSwitcher = me.data?.organisation != null;
  const [scope, setScope] = useState<Scope>("mine");
  // The Archived toggle (owner, round 11), as on Tasks: the archived
  // projects of the open scope. Off, the queries are as before.
  const [archived, setArchived] = useState(false);
  const archivedFilter = archived ? { status: "archived" as const } : {};
  // Paged by the server, 20 a page (round 12); "Show more" asks for the
  // next page of the list on screen, as on Tasks.
  const projects = useProjectsPaged(
    hasSwitcher ? { scope, ...archivedFilter } : archived ? archivedFilter : undefined,
  );
  // The server orders the projects by their last activity
  // (`last_activity_at`, round 12) and the page keeps its order, so a page
  // that arrives with "Show more" lands below the rows already shown.
  const { rows, more } = pagedProjects(projects);
  const create = useCreateProject();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  // An archived row folds away where it stood (owner, round 12).
  const { shown, depart } = useDepartingRows(rows, (project) => project.project_id);
  // After "Show more", focus moves to the first project that arrived (as on
  // Tasks), found by id: a project already listed is dropped from the new
  // page, so the arrivals' position is not the old row count.
  const listRef = useRef<HTMLUListElement>(null);
  const listedBefore = useRef<ReadonlySet<string> | null>(null);
  useEffect(() => {
    const before = listedBefore.current;
    if (before === null) return;
    const index = rows.findIndex((project) => !before.has(project.project_id));
    if (index === -1) return;
    listedBefore.current = null;
    listRef.current?.querySelectorAll<HTMLAnchorElement>(":scope > li a[href]")[index]?.focus();
  }, [rows]);
  const showOwner = showOwnerColumn(hasSwitcher, rows, scope);
  const isAdminWideList = hasSwitcher && me.data?.is_admin === true && scope === "all";
  const ownerlessLabel = isAdminWideList ? TENANCY_COPY.noOrganisation : TENANCY_COPY.ownerlessRow;

  return (
    <main className={PAGE_COLUMN_CLASS}>
      <PageHeader
        title={PROJECT.many}
        actions={
          // The header keeps only the primary (owner, round 11). It stays
          // in its slot while the form is open, disabled, so the header
          // does not reflow and the form's Create is the one blue fill on
          // the page.
          <PagePrimary onClick={() => setCreating(true)} disabled={creating}>
            New {PROJECT.lower}
          </PagePrimary>
        }
        filters={hasSwitcher ? <ScopeSwitcher scope={scope} onChange={setScope} /> : null}
        // As on Tasks: the admin's note, then the magnifier.
        aside={
          <div className="flex flex-wrap items-center justify-end gap-x-2 gap-y-2">
            {isAdminWideList && (
              <p role="status" className="text-meta font-semibold text-grey">
                {TENANCY_COPY.adminWiderList}
              </p>
            )}
            <FindPopover
              items={rows.map((project) => ({
                id: project.project_id,
                label: project.name,
                href: `/projects/${project.project_id}`,
                updatedAt: project.last_activity_at,
              }))}
              copy={{ label: COPY.findProject, noun: PROJECT.lowerMany }}
              className="-mr-3"
            />
          </div>
        }
      />

      {creating && (
        <Card className="mt-4 max-w-md p-5">
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
            <label className="text-meta font-semibold text-navy" htmlFor="new-project-name">
              {PROJECT.one} name
            </label>
            <input
              id="new-project-name"
              autoFocus
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="border border-line-2 bg-paper px-3 py-2.5 text-body"
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

      <div className="mt-4">
        {/* With the archive open, the list says what it is (owner, round 11). */}
        {archived && <h2 className={ARCHIVED_HEADING_CLASS}>Archived</h2>}
        {projects.isPending && <ListSkeleton label={`Loading ${PROJECT.lowerMany}`} />}

        {/* A page after the first that fails keeps the rows and offers Retry
            under them; only a failed first page replaces the list. */}
        {projects.isError && !projects.isFetchNextPageError && (
          <ListError actionLabel="Try again" onRetry={() => void projects.refetch()}>
            Couldn&apos;t load your {PROJECT.lowerMany}.
          </ListError>
        )}

        {projects.data !== undefined &&
          !projects.isError &&
          rows.length === 0 &&
          !creating &&
          (archived ? (
            <ListEmpty label={`No archived ${PROJECT.lowerMany}`} />
          ) : (
            <ListEmpty label={`No ${PROJECT.lowerMany} yet`}>
              A {PROJECT.lower} groups related {TASK.lowerMany} under one name.
            </ListEmpty>
          ))}

        {rows.length > 0 && (
          <ul ref={listRef} role="list" className={listFrameClass}>
            {shown.map(({ row: project, leaving }) => (
              <li key={project.project_id} className="group border-b border-line last:border-b-0">
                <RowFold leaving={leaving}>
                  <ProjectRowWithMenu
                    project={project}
                    lastUpdated={project.last_activity_at}
                    showOwner={showOwner}
                    ownerlessLabel={ownerlessLabel}
                    onArchived={() => depart(project.project_id)}
                  />
                </RowFold>
              </li>
            ))}
          </ul>
        )}

        {more.error && rows.length > 0 && (
          <div className="mt-4">
            <ListError actionLabel="Retry" onRetry={more.onRetry}>
              Couldn&apos;t load your {PROJECT.lowerMany}.
            </ListError>
          </div>
        )}

        {/* The list's foot: "Show more" while the server holds more (round
            12), the archived toggle at the right (round 11). */}
        <ListFootRow
          start={
            rows.length > 0 && more.hasMore && !more.error ? (
              <ShowMore
                more={more}
                onShowMore={() => {
                  listedBefore.current = new Set(rows.map((project) => project.project_id));
                  more.onShowMore();
                }}
              />
            ) : null
          }
          end={<ArchivedToggle pressed={archived} onToggle={() => setArchived((on) => !on)} />}
        />
      </div>
    </main>
  );
}

type ProjectRow = components["schemas"]["ProjectOut"];

/**
 * One project row with its menu (owner, round 12): the row's link, and
 * beside it, for the project's owner only, the control that opens Rename
 * and Archive. Rename turns the row into the name's field; Archive, once
 * confirmed, folds the row away (`onArchived`). An archived project offers
 * Rename only.
 */
function ProjectRowWithMenu({
  project,
  lastUpdated,
  showOwner,
  ownerlessLabel,
  onArchived,
}: {
  project: ProjectRow;
  lastUpdated: string;
  showOwner: boolean;
  ownerlessLabel: string;
  onArchived: () => void;
}) {
  const update = useUpdateProject(project.project_id);
  const archive = useArchiveProject(project.project_id);
  const [editing, setEditing] = useState(false);
  const control = useRef<HTMLButtonElement>(null);
  const pending = update.isPending || archive.isPending;
  const label = `${PROJECT.one} settings`;
  const date = formatListDate(lastUpdated);
  const owner = project.is_owner
    ? "You"
    : project.owner_display !== null
      ? scrub(project.owner_display)
      : ownerlessLabel;
  const count = project.task_count === 1 ? `1 ${TASK.lower}` : `${project.task_count} ${TASK.lowerMany}`;

  if (editing) {
    return (
      <RowRenameField
        name={project.name}
        label={label}
        fieldLabel={`${PROJECT.one} name`}
        rename={(next, done) => update.mutate({ name: next }, { onSuccess: done.onSuccess, onError: done.onError })}
        renameError={`The ${PROJECT.lower} couldn't be renamed. Try again.`}
        pending={pending}
        onClose={() => {
          setEditing(false);
          window.setTimeout(() => control.current?.focus(), 0);
        }}
      />
    );
  }

  return (
    <>
      <Link
        to={`/projects/${project.project_id}`}
        // Its content in order, as the task rows (round 10).
        aria-label={rowAccessibleName([
          scrub(project.name),
          showOwner && owner !== TENANCY_COPY.ownerlessRow ? owner : null,
          count,
          date,
        ])}
        className={showOwner ? projectListRowGridClassWithOwner : projectListRowGridClass}
      >
        <span className={`${rowNameCellClass} font-semibold text-navy max-md:col-span-2`}>
          {scrub(project.name)}
        </span>
        {showOwner && <span className={`${rowOwnerCellClass} max-md:hidden`}>{owner}</span>}
        <span className={`${rowFigureCellClass} max-md:text-left`}>
          <Figures text={count} />
        </span>
        <time dateTime={lastUpdated} className={rowFigureCellClass}>
          <Figures text={date} />
        </time>
      </Link>
      {project.is_owner && (
        <RowMenuControl
          label={label}
          name={project.name}
          controlRef={control}
          pending={pending}
          onRename={() => setEditing(true)}
          archive={
            project.archived_at != null
              ? undefined
              : (_, done) =>
                  archive.mutate(undefined, {
                    onSuccess: () => {
                      done.onSuccess();
                      onArchived();
                    },
                    onError: done.onError,
                  })
          }
          archiveSentence={`Archiving removes this ${PROJECT.lower} from your active ${PROJECT.lowerMany}. Its ${TASK.lowerMany} stay as they are.`}
          archiveError={`The ${PROJECT.lower} couldn't be archived. Try again.`}
        />
      )}
    </>
  );
}

/**
 * A paged project list's rows and its foot, as `pagedTasks` for tasks: the
 * pages in order, a project already listed dropped (one that changes
 * between two requests can cross a page boundary).
 *
 * Args:
 *   result: A `useProjectsPaged` result.
 *
 * Returns:
 *   The loaded rows and the foot's state.
 */
function pagedProjects(result: ReturnType<typeof useProjectsPaged>): {
  rows: ProjectRow[];
  more: MoreTasks;
} {
  const seen = new Set<string>();
  const rows: ProjectRow[] = [];
  for (const page of result.data?.pages ?? []) {
    for (const row of page.data) {
      if (seen.has(row.project_id)) continue;
      seen.add(row.project_id);
      rows.push(row);
    }
  }
  const askForNext = () => void result.fetchNextPage();
  return {
    rows,
    more: {
      hasMore: result.hasNextPage,
      loading: result.isFetchingNextPage,
      error: result.isFetchNextPageError,
      onShowMore: askForNext,
      onRetry: askForNext,
    },
  };
}

/**
 * The project's row from any Projects list already in the cache (every
 * scope), so a project opened from the Projects page has its name,
 * description and visibility on the first frame instead of after its own
 * request: the header is whole before anything below it draws, and nothing
 * moves when the detail lands and replaces it.
 */
function listedProject(client: QueryClient, projectId: string): ProjectRow | undefined {
  // Both shapes share the key's head: a picker's one page (`useProjects`)
  // and the Projects page's pages (`useProjectsPaged`, round 12).
  const lists = client.getQueriesData<{ data: ProjectRow[] } | { pages: { data: ProjectRow[] }[] }>({
    queryKey: queryKeys.projects().slice(0, 2),
  });
  for (const [, cached] of lists) {
    if (cached === undefined) continue;
    const pages = "pages" in cached ? cached.pages : [cached];
    for (const page of pages) {
      const row = page.data.find((candidate) => candidate.project_id === projectId);
      if (row !== undefined) return row;
    }
  }
  return undefined;
}

/** One project: its tasks, with the same list chrome as the Tasks page. */
export function ProjectDetailView() {
  const { projectId = "" } = useParams();
  const me = useMe();
  const project = useProject(projectId);
  const queryClient = useQueryClient();
  const shown = project.data ?? listedProject(queryClient, projectId);
  // Server-side `project_id` filter (task 033 phase 10a) — this used to
  // filter the global 50-row tasks page client-side, silently
  // under-reporting once a project's membership (or the caller's visible
  // estate) grew past that page. `page_size` is raised to the same 200-row
  // server-max convention as the overview page above: without it this call
  // still falls back to the 50-row default and a project with 51+ tasks
  // would silently truncate.
  // Past the 200-row page, "Show more" asks for the next (round 10).
  const tasksQuery = useTasksPaged({
    project_id: projectId,
    page_size: PROJECT_TASKS_PAGE_SIZE,
  });
  const { rows: tasks, more } = pagedTasks(tasksQuery);
  const updateProject = useUpdateProject(projectId);
  const toast = useToast();
  useDocumentTitle(shown?.name, PROJECT.one);

  const hasSwitcher = me.data?.organisation != null;
  const showOwner = showOwnerColumn(hasSwitcher, tasks);
  const isAdminWideList = hasSwitcher && me.data?.is_admin === true;
  const ownerlessLabel = isAdminWideList ? TENANCY_COPY.noOrganisation : TENANCY_COPY.ownerlessRow;

  const changeVisibility = (next: "org" | "private") => {
    updateProject.mutate(
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
    <main className={PAGE_COLUMN_CLASS}>
      <PageHeader
        context={<PageBackLink to="/projects">← {PROJECT.many}</PageBackLink>}
        // From the Projects list's cache when we came from there; otherwise
        // empty while the project loads, keeping its line box.
        // The name with its menu, Rename and Archive (owner, round 11).
        title={
          shown === undefined ? (
            ""
          ) : (
            <ProjectName
              projectId={projectId}
              name={shown.name}
              isOwner={shown.is_owner}
              archived={shown.archived_at != null}
            />
          )
        }
        actions={<PagePrimary to={newTaskHref(projectId)}>{COPY.newTask}</PagePrimary>}
        filters={
          shown?.description != null ? (
            <p className="max-w-prose text-body text-grey">{scrub(shown.description)}</p>
          ) : null
        }
        // The magnifier, then Make private (round 11: the header keeps
        // only the primary).
        aside={
          <div className="flex items-center gap-x-2">
            <FindTasks rows={tasks} className={shown === undefined ? "-mr-3" : undefined} />
            {shown !== undefined && (
              <VisibilityControl
                visibility={shown.visibility}
                isOwner={shown.is_owner}
                pending={updateProject.isPending}
                onChange={changeVisibility}
                // -mr-3: the label's right edge on the column's, under the primary.
                className={`${PAGE_CONTROL_CLASS} -mr-3`}
              />
            )}
          </div>
        }
      />

      <div className="mt-4">
        <TaskListPanel
          rows={tasks}
          isPending={project.isPending || tasksQuery.isPending}
          isError={project.isError || (tasksQuery.isError && !tasksQuery.isFetchNextPageError)}
          onRetry={() => {
            void project.refetch();
            void tasksQuery.refetch();
          }}
          loaded={project.data !== undefined && tasksQuery.data !== undefined}
          showOwner={showOwner}
          ownerlessLabel={ownerlessLabel}
          more={more}
          empty={
            <ListEmpty label={COPY.noTasks}>
              {TASK.many} you start here join this {PROJECT.lower}.
            </ListEmpty>
          }
        />
      </div>
    </main>
  );
}
