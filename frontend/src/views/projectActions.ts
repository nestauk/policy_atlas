import { useCreateProject, useUpdateTask } from "../api/mutations";

/** What an action calls once it has settled. */
type Settled<T> = { onSuccess?: (value: T) => void; onError?: () => void };

/**
 * Make a project from a name (round 13; defined once): the one way the app
 * creates a project, from the New page's picker, the task menu's step, the
 * Share page and the Projects page's form alike (`useCreateProject`).
 *
 * Returns:
 *   `make(name, settled)`, calling back with the new project's id and name,
 *   and whether a make is under way.
 */
export function useMakeProject(): {
  make: (name: string, settled?: Settled<{ projectId: string; name: string }>) => void;
  isPending: boolean;
} {
  const create = useCreateProject();
  return {
    make: (name, settled) =>
      create.mutate(
        { name: name.trim() },
        {
          onSuccess: (project) => settled?.onSuccess?.({ projectId: project.project_id, name: project.name }),
          onError: () => settled?.onError?.(),
        },
      ),
    isPending: create.isPending,
  };
}

/**
 * Add a task to a project (round 13; defined once): the task menu's "Add to
 * project" (rows and header) and the Share page's add run this. The task's
 * `project_ids` with the chosen one added, through `useUpdateTask`.
 *
 * Args:
 *   taskId: The task.
 *   projectIds: Its projects now.
 *
 * Returns:
 *   `add(projectId, settled)`; the error reaches `onError` as the mutation
 *   threw it, so a caller can say the server's refusal.
 */
export function useAddTaskToProject(
  taskId: string,
  projectIds: readonly string[] | null | undefined,
): { add: (projectId: string, settled?: { onSuccess?: () => void; onError?: (error: unknown) => void }) => void; isPending: boolean } {
  const update = useUpdateTask(taskId);
  return {
    add: (projectId, settled) =>
      update.mutate(
        { project_ids: [...(projectIds ?? []), projectId] },
        { onSuccess: () => settled?.onSuccess?.(), onError: (error) => settled?.onError?.(error) },
      ),
    isPending: update.isPending,
  };
}
