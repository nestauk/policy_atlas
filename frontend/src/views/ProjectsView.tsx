import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import type { components } from "../api/gen/types";
import { queryKeys, useMe, useProject, useProjects, useTasks } from "../api/queries";
import { useCreateProject, useUpdateProject } from "../api/mutations";
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
  listFrameClass,
  newTaskHref,
  newestTaskUpdateByProject,
  projectLastUpdated,
  projectListRowGridClass,
  projectListRowGridClassWithOwner,
  rowFigureCellClass,
  rowNameCellClass,
  showOwnerColumn,
  sortProjectsByLastUpdated,
} from "./listPageChrome";
import type { Scope } from "./ScopeSwitcher";
import { ScopeSwitcher } from "./ScopeSwitcher";
import {
  ListEmpty,
  ListError,
  ListSkeleton,
  TaskListActions,
  TaskListPanel,
} from "./TaskListPanel";
import { VisibilityControl, visibilityOutcomeLine } from "./VisibilityControl";

/**
 * Projects: named groupings of tasks, and nothing else.
 *
 * A task holds no plan, no run and no evidence of its own, so the page
 * shows a name and a count and stops there. Anything more would imply the
 * grouping has a state, which it does not.
 */
/** `ProjectOut` carries a derived `task_count` but no last-task-updated
 *  timestamp, so this overview still leans on the global tasks page to
 *  derive "most recently active" per project (`newestTaskUpdateByProject`
 *  below) — asking per-project would be N+1 requests for a list page.
 *  Server page-size cap (`PAGE_SIZE_MAX`, web-api.md § Pagination): raised
 *  from the 50-row default so this remains an approximation rather than
 *  systematically wrong, not a fix — a workspace with more than 200 active
 *  tasks across projects can still miss a newer update that falls
 *  outside this page. `ProjectDetailView` does not share the *last-update*
 *  limitation: it fetches its own member list via `project_id`, which is
 *  exact up to the same 200-row cap (task 033 phase 10a) rather than the
 *  50-row default. */
const PROJECTS_OVERVIEW_TASKS_PAGE_SIZE = 200;

export function ProjectsView() {
  useDocumentTitle(PROJECT.many);
  const me = useMe();
  // Hidden entirely with no organisation (rubric 14's dark-launch invariant):
  // an unenrolled caller's page — including its queries — stays unchanged.
  const hasSwitcher = me.data?.organisation != null;
  const [scope, setScope] = useState<Scope>("mine");
  const projects = useProjects(hasSwitcher ? { scope } : undefined);
  const tasksQuery = useTasks(
    hasSwitcher
      ? { page_size: PROJECTS_OVERVIEW_TASKS_PAGE_SIZE, scope }
      : { page_size: PROJECTS_OVERVIEW_TASKS_PAGE_SIZE },
  );
  const create = useCreateProject();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const taskUpdatedAt = newestTaskUpdateByProject(tasksQuery.data?.data ?? []);
  const rows = sortProjectsByLastUpdated(projects.data?.data ?? [], taskUpdatedAt);
  const showOwner = showOwnerColumn(hasSwitcher, rows);
  const isAdminWideList = hasSwitcher && me.data?.is_admin === true && scope === "all";
  const ownerlessLabel = isAdminWideList ? TENANCY_COPY.noOrganisation : TENANCY_COPY.ownerlessRow;

  return (
    <main className={PAGE_COLUMN_CLASS}>
      <PageHeader
        title={PROJECT.many}
        actions={
          // Stays in its slot while the form is open, disabled, so the
          // header does not reflow and the form's Create is the one blue
          // fill on the page.
          <PagePrimary onClick={() => setCreating(true)} disabled={creating}>
            New {PROJECT.lower}
          </PagePrimary>
        }
        filters={hasSwitcher ? <ScopeSwitcher scope={scope} onChange={setScope} /> : null}
        aside={
          isAdminWideList ? (
            <p role="status" className="text-meta font-semibold text-grey">
              {TENANCY_COPY.adminWiderList}
            </p>
          ) : null
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

      <div className="mt-4">
        {projects.isPending && <ListSkeleton label={`Loading ${PROJECT.lowerMany}`} />}

        {projects.isError && (
          <ListError actionLabel="Try again" onRetry={() => void projects.refetch()}>
            Couldn&apos;t load your {PROJECT.lowerMany}.
          </ListError>
        )}

        {projects.data !== undefined && projects.data.data.length === 0 && !creating && (
          <ListEmpty label={`No ${PROJECT.lowerMany} yet`}>
            A {PROJECT.lower} groups related {TASK.lowerMany} under one name.
          </ListEmpty>
        )}

        {(projects.data?.data.length ?? 0) > 0 && (
          <ul role="list" className={listFrameClass}>
            {rows.map((project) => {
              const lastUpdated = projectLastUpdated(project, taskUpdatedAt);
              return (
                <li key={project.project_id} className="border-b border-line last:border-b-0">
                  <Link
                    to={`/projects/${project.project_id}`}
                    className={showOwner ? projectListRowGridClassWithOwner : projectListRowGridClass}
                  >
                    <span
                      className={`${rowNameCellClass} font-semibold text-navy max-md:col-span-2`}
                    >
                      {scrub(project.name)}
                    </span>
                    {showOwner && (
                      <span className={`${rowFigureCellClass} text-meta max-md:hidden`}>
                        {project.owner_display !== null
                          ? scrub(project.owner_display)
                          : ownerlessLabel}
                      </span>
                    )}
                    <span className={`${rowFigureCellClass} text-meta max-md:text-left`}>
                      <Figures
                        text={
                          project.task_count === 1
                            ? `1 ${TASK.lower}`
                            : `${project.task_count} ${TASK.lowerMany}`
                        }
                      />
                    </span>
                    <time dateTime={lastUpdated} className={`${rowFigureCellClass} text-caption tabular-nums`}>
                      {new Date(lastUpdated).toLocaleDateString()}
                    </time>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </main>
  );
}

type ProjectRow = components["schemas"]["ProjectOut"];

/**
 * The project's row from any Projects list already in the cache (every
 * scope), so a project opened from the Projects page has its name,
 * description and visibility on the first frame instead of after its own
 * request: the header is whole before anything below it draws, and nothing
 * moves when the detail lands and replaces it.
 */
function listedProject(client: QueryClient, projectId: string): ProjectRow | undefined {
  const lists = client.getQueriesData<{ data: ProjectRow[] }>({
    queryKey: queryKeys.projects().slice(0, 2),
  });
  for (const [, page] of lists) {
    const row = page?.data.find((candidate) => candidate.project_id === projectId);
    if (row !== undefined) return row;
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
  const tasksQuery = useTasks({
    project_id: projectId,
    page_size: PROJECTS_OVERVIEW_TASKS_PAGE_SIZE,
  });
  const updateProject = useUpdateProject(projectId);
  const toast = useToast();
  useDocumentTitle(shown?.name, PROJECT.one);

  const tasks = tasksQuery.data?.data ?? [];
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
        title={shown === undefined ? "" : scrub(shown.name)}
        actions={<TaskListActions rows={tasks} newTaskHref={newTaskHref(projectId)} />}
        filters={
          shown?.description != null ? (
            <p className="max-w-prose text-body text-grey">{scrub(shown.description)}</p>
          ) : null
        }
        aside={
          shown !== undefined ? (
            <VisibilityControl
              visibility={shown.visibility}
              isOwner={shown.is_owner}
              pending={updateProject.isPending}
              onChange={changeVisibility}
              // -mr-3: the label's right edge on the column's, under the primary.
              className={`${PAGE_CONTROL_CLASS} -mr-3`}
            />
          ) : null
        }
      />

      <div className="mt-4">
        <TaskListPanel
          rows={tasks}
          isPending={project.isPending || tasksQuery.isPending}
          isError={project.isError || tasksQuery.isError}
          onRetry={() => {
            void project.refetch();
            void tasksQuery.refetch();
          }}
          loaded={project.data !== undefined && tasksQuery.data !== undefined}
          showOwner={showOwner}
          ownerlessLabel={ownerlessLabel}
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
