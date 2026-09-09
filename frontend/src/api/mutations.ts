import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { components } from "./gen/types";
import { queryKeys, useApiClient } from "./queries";

type CheckInResponseBody =
  | components["schemas"]["OptionResponse"]
  | components["schemas"]["FreeTextResponse"]
  | components["schemas"]["FreeTextConfirmResponse"]
  | components["schemas"]["AbortResponse"];

/** Throw the response's error envelope so callers can map `error.code`. */
function raise(error: unknown, status?: number): never {
  const body = error as { error?: { code?: string; message?: string } } | undefined;
  const code = body?.error?.code ?? "internal";
  const message = body?.error?.message ?? "Something went wrong";
  throw Object.assign(new Error(message), { code, status });
}

/**
 * Start a task from a question (plan D4).
 *
 * Two calls, no backend change: create the task, then post the same
 * question as its first planning turn, so the conversation opens with the
 * words the person actually typed rather than a system greeting.
 *
 * The task's name is derived from the question here (D5). The planner's own
 * `plan.title` is deliberately not written back — that would be new
 * behaviour — so a task shows its derived name until renamed.
 */
export function useCreateTask() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { question: string; projectId?: string | null }) => {
      const question = input.question.trim();
      const { data: task, error, response } = await client.POST("/api/v1/tasks", {
        body: { name: taskNameFromQuestion(question), question },
      });
      if (task === undefined) raise(error, response.status);

      if (input.projectId != null) {
        await client.PATCH("/api/v1/tasks/{task_id}", {
          params: { path: { task_id: task.task_id } },
          body: { project_id: input.projectId },
        });
      }

      // The opening turn. A failure here leaves a real, usable task whose
      // conversation is simply empty, so it is not worth unwinding the
      // creation — the person can just type the question again.
      await client.POST("/api/v1/tasks/{task_id}/planning-turns", {
        params: { path: { task_id: task.task_id } },
        body: { message: question, client_turn_id: crypto.randomUUID() },
      });
      return task;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

/** A short display name from the question (plan D5): no trailing question
 *  mark, and clipped on a word boundary rather than mid-word. */
export function taskNameFromQuestion(question: string, max = 80): string {
  const cleaned = question.trim().replace(/\s+/g, " ").replace(/\?+$/, "").trim();
  if (cleaned.length <= max) return cleaned;
  const clipped = cleaned.slice(0, max);
  const lastSpace = clipped.lastIndexOf(" ");
  return `${(lastSpace > max / 2 ? clipped.slice(0, lastSpace) : clipped).trimEnd()}…`;
}

/** `POST /api/v1/projects` — create a task (the screen word). */
export function useCreateProject() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; description?: string | null }) => {
      const { data, error, response } = await client.POST("/api/v1/projects", { body });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
}

/** `PATCH .../{id}` — partial update (rename and/or question edit). */
export function useUpdateTask(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      name?: string | null;
      question?: string | null;
      project_id?: string | null;
    }) => {
      const { data, error, response } = await client.PATCH("/api/v1/tasks/{task_id}", {
        params: { path: { task_id: taskId } },
        body,
      });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    // The bare "tasks" root covers BOTH this task's detail key and the
    // tasks-list key (["tasks", "list", …]) — a rename must refresh the
    // landing card, not just the workspace header (F.2 finding, 2026-07-29).
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

/** `POST .../archive` — idempotent soft-delete (409 `run_active` while running). */
export function useArchiveTask(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await client.POST(
        "/api/v1/tasks/{task_id}/archive",
        { params: { path: { task_id: taskId } } },
      );
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

/** `POST .../planning-turns` — one real planner turn. `clientTurnId` is
 *  minted by the caller per logical turn (one per submitted message, not
 *  per send attempt) so that retrying the same submission reuses the id
 *  rather than minting a fresh one the server would treat as a new turn. */
export function usePlanningTurn(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { message: string; clientTurnId: string }) => {
      const { data, error, response } = await client.POST(
        "/api/v1/tasks/{task_id}/planning-turns",
        {
          params: { path: { task_id: taskId } },
          body: { message: input.message, client_turn_id: input.clientTurnId },
        },
      );
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.taskRoot(taskId) }),
  });
}

/** `PATCH .../plan` — persist typed document edits onto the approved plan. */
export function usePatchPlan(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components["schemas"]["PlanPatchIn"]) => {
      const { data, error, response } = await client.PATCH("/api/v1/tasks/{task_id}/plan", {
        params: { path: { task_id: taskId } },
        body,
      });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.taskRoot(taskId) }),
  });
}

/** `POST .../runs` — dispatch the approved plan's walk (409 while one is active). */
export function useStartRun(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await client.POST("/api/v1/tasks/{task_id}/runs", {
        params: { path: { task_id: taskId } },
        body: {},
      });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.taskRoot(taskId) }),
  });
}

/** `POST .../check-ins/{id}/response` — option/abort answers and the free-text
 *  compile→confirm ladder (202 carries the compiled render + confirm token). */
export function useAnswerCheckIn(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { checkInId: string; body: CheckInResponseBody }) => {
      const { data, error, response } = await client.POST(
        "/api/v1/tasks/{task_id}/check-ins/{check_in_id}/response",
        {
          params: { path: { task_id: taskId, check_in_id: input.checkInId } },
          body: input.body,
        },
      );
      if (response.status === 202 && data !== undefined) {
        return { kind: "compiled" as const, compiled: data };
      }
      if (!response.ok) raise(error, response.status);
      return { kind: "answered" as const };
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.taskRoot(taskId) }),
  });
}
