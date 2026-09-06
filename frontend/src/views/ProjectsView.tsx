import { useState } from "react";
import { Link, useParams } from "react-router";

import { useMe, useProject, useProjects, useTasks } from "../api/queries";
import { useCreateProject, useUpdateProject } from "../api/mutations";
import { isConflictCode, conflictSentences } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { PROJECT, TASK, TENANCY_COPY } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";
import { useToast } from "../ui/radix/Toast";
import {
  listPageTitleClass,
  listSecondaryActionClass,
  newTaskHref,
  newestTaskUpdateByProject,
  projectLastUpdated,
  showOwnerColumn,
  sortProjectsByLastUpdated,
} from "./listPageChrome";
import type { Scope } from "./ScopeSwitcher";
import { ScopeSwitcher } from "./ScopeSwitcher";
import { TaskListActions, TaskListPanel } from "./TaskListPanel";
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
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className={listPageTitleClass}>{PROJECT.many}</h1>
        <div className="flex items-center gap-4">
          {hasSwitcher && <ScopeSwitcher scope={scope} onChange={setScope} />}
          {!creating && (
            <Button className="px-6 py-3.5 text-body" onClick={() => setCreating(true)}>
              New {PROJECT.lower}
            </Button>
          )}
        </div>
      </header>

      {isAdminWideList && (
        <p role="status" className="mb-4 text-meta font-semibold text-grey">
          {TENANCY_COPY.adminWiderList}
        </p>
      )}

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

      {projects.isPending && (
        <div aria-busy="true" aria-label={`Loading ${PROJECT.lowerMany}`} className="space-y-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-14 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {projects.data !== undefined && projects.data.data.length === 0 && !creating && (
        <Card role="status" className="mx-auto max-w-md p-8 text-center">
          <h2 className="text-heading font-extrabold text-navy">No {PROJECT.lowerMany} yet</h2>
          <p className="mt-1.5 text-body text-grey">
            A {PROJECT.lower} groups related {TASK.lowerMany} under one name.
          </p>
        </Card>
      )}

      {(projects.data?.data.length ?? 0) > 0 && (
        <ul role="list" className="border border-line-2 bg-paper">
          {rows.map((project) => {
            const lastUpdated = projectLastUpdated(project, taskUpdatedAt);
            return (
              <li key={project.project_id} className="border-b border-line last:border-b-0">
                <Link
                  to={`/projects/${project.project_id}`}
                  className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3.5 no-underline hover:bg-blue-tint-2"
                >
                  <span className="min-w-0 flex-1 text-body font-semibold text-navy">
                    {scrub(project.name)}
                  </span>
                  {showOwner && (
                    <span className="text-meta text-grey">
                      {project.owner_display !== null ? scrub(project.owner_display) : ownerlessLabel}
                    </span>
                  )}
                  <span className="text-meta text-grey">
                    {project.task_count === 1
                      ? `1 ${TASK.lower}`
                      : `${project.task_count} ${TASK.lowerMany}`}
                  </span>
                  <time
                    dateTime={lastUpdated}
                    className="w-28 shrink-0 text-right text-caption tabular-nums text-grey"
                  >
                    {new Date(lastUpdated).toLocaleDateString()}
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

/** One task: its tasks, with the same list chrome as the Tasks page. */
export function ProjectDetailView() {
  const { projectId = "" } = useParams();
  const me = useMe();
  const project = useProject(projectId);
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
  useDocumentTitle(project.data?.name, PROJECT.one);

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
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <Link to="/projects" className={listSecondaryActionClass}>
            ← {PROJECT.many}
          </Link>
          <h1 className={`${listPageTitleClass} mt-2`}>
            {project.data === undefined ? "" : scrub(project.data.name)}
          </h1>
          {project.data?.description != null && (
            <p className="mt-2 max-w-prose text-body text-grey">
              {scrub(project.data.description)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-4">
          {project.data !== undefined && (
            <VisibilityControl
              visibility={project.data.visibility}
              isOwner={project.data.is_owner}
              pending={updateProject.isPending}
              onChange={changeVisibility}
            />
          )}
          <TaskListActions rows={tasks} newTaskHref={newTaskHref(projectId)} />
        </div>
      </header>

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
      />
    </main>
  );
}
