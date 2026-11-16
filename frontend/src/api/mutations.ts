import { useMutation, useMutationState, useQueryClient } from "@tanstack/react-query";
import { askForFinishAlerts } from "../lib/askForAlerts";

import { useAuth } from "../auth";
import { buildAuthHeaders } from "./authMiddleware";
import { apiBaseUrl } from "./client";
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
 * ONE create call (task 044, C10): the kind of work, the project and the
 * tasks it starts from all travel in the body and are written in one
 * transaction, so a create either lands whole or not at all. The separate
 * PATCH this used to make could fail after the task existed, leaving a real
 * but unassigned task — and "Starts from" cannot be built on a flow with
 * that failure mode.
 *
 * The opening task_agent turn is not posted here (task 058, N9): the New Task
 * screen navigates to the Agent tab at once, and the tab streams the opening
 * turn with the words the person typed, so the planner's reply arrives where
 * they are looking instead of behind a blocked submit button.
 *
 * The task's name is derived from the question here (D5). The task_agent's own
 * `plan.title` is deliberately not written back — that would be new
 * behaviour — so a task shows its derived name until renamed.
 */
export function useCreateTask() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      question: string;
      projectId?: string | null;
      capability?: components["schemas"]["TaskCreate"]["capability"];
      fromTaskIds?: string[];
    }) => {
      const question = input.question.trim();
      const { data: task, error, response } = await client.POST("/api/v1/tasks", {
        body: {
          name: taskNameFromQuestion(question),
          question,
          capability: input.capability ?? "evidence_search",
          project_ids: input.projectId != null ? [input.projectId] : [],
          from_task_ids: input.fromTaskIds ?? [],
        },
      });
      if (task === undefined) raise(error, response.status);
      return task;
    },
    // "projects" is invalidated too, symmetric with `useUpdateTask`/
    // `useArchiveTask` below: a successful `projectId` assignment above
    // changes that project's derived `task_count`, a cross-family effect
    // the project list would otherwise keep showing stale until an
    // unrelated refetch.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
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
    // `visibility` (task 033 phase 10b): owner-only, and refused 422 combined
    // with `project_ids` in one body — see `TaskUpdate`'s own docstring.
    mutationFn: async (body: components["schemas"]["TaskUpdate"]) => {
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
    // "projects" is invalidated too (task 033 phase 10a): `visibility` and
    // `project_ids` are both patchable here, and either can change a
    // project's derived `task_count` or member visibility — a cross-family
    // effect from a task-family mutation, the same class of bug the
    // project-PATCH cascade below has to cover in the other direction.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
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
    // Same cross-family reasoning as `useUpdateTask`: archiving removes
    // the task from its project's active `task_count`.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

/** `POST /api/v1/projects/{id}/archive` (task 058, rounds 11 and 14): the
 *  owner archives a project. It leaves the default Projects list and is
 *  listed under `status: "archived"`. In the same call the server archives
 *  each of the caller's own active tasks in it that is in no other active
 *  project and has no run under way; any other task is left as it is.
 *  Archiving an archived project changes nothing. */
export function useArchiveProject(projectId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await client.POST(
        "/api/v1/projects/{project_id}/archive",
        { params: { path: { project_id: projectId } } },
      );
      if (data === undefined) raise(error, response.status);
      return data;
    },
    // The archived tasks leave the task lists, so they refetch too.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

/**
 * `PATCH /api/v1/projects/{id}` — rename, re-describe, or (supplying
 * `visibility`) run the server's i.4 visibility cascade onto every member
 * task in one transaction (contract § 6). No component calls this yet —
 * the visibility control lands in phase 10b/10c — but the cache wiring is
 * data-layer work: a cascade rewrites rows in the *task* family from a
 * *project* mutation, so both families are invalidated by prefix (not the
 * exact filtered key) so every `scope` variant currently cached is covered,
 * or a card would keep showing the pre-cascade visibility until an
 * unrelated refetch.
 */
export function useUpdateProject(projectId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components["schemas"]["ProjectUpdate"]) => {
      const { data, error, response } = await client.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: projectId } },
        body,
      });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

/** One event of the planner's turn stream (task 058, N9). */
export type TaskAgentStreamEvent =
  | components["schemas"]["TaskAgentProgressEvent"]
  | components["schemas"]["TaskAgentDeltaEvent"]
  | components["schemas"]["TaskAgentCompletedEvent"]
  | components["schemas"]["TaskAgentFailedEvent"];

/** The stream ended before its one terminal event: the connection dropped.
 *  The turn is durable and finishes on the server, so the caller re-reads the
 *  transcript rather than retrying. */
export class TaskAgentStreamInterruptedError extends Error {
  constructor() {
    super("The connection dropped before the reply finished.");
    this.name = "TaskAgentStreamInterruptedError";
  }
}

function narrowTaskAgentEvent(value: unknown): TaskAgentStreamEvent {
  const event = value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
  if (event.type === "progress" && typeof event.label === "string") return event as TaskAgentStreamEvent;
  if (event.type === "delta" && typeof event.text === "string") return event as TaskAgentStreamEvent;
  if (event.type === "completed" && event.turn !== null && typeof event.turn === "object") {
    return event as TaskAgentStreamEvent;
  }
  if (event.type === "failed" && event.error !== null && typeof event.error === "object") {
    return event as TaskAgentStreamEvent;
  }
  throw Object.assign(new Error("The reply stream contained an invalid event."), { code: "internal" });
}

/**
 * Read a planner turn's NDJSON body, handing each event over in wire order,
 * up to and including its one terminal event (`completed` or `failed`).
 *
 * Args:
 *   body: The streamed response body.
 *   onEvent: Receives each event.
 *
 * Returns:
 *   The terminal event.
 *
 * Raises:
 *   TaskAgentStreamInterruptedError: The body ended before a terminal event.
 */
export async function consumeTaskAgentStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: TaskAgentStreamEvent) => void,
): Promise<TaskAgentStreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminal: TaskAgentStreamEvent | null = null;
  const consumeLine = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line.trim() === "" || terminal !== null) return;
    let value: unknown;
    try {
      value = JSON.parse(line);
    } catch {
      throw Object.assign(new Error("The reply stream contained malformed JSON."), { code: "internal" });
    }
    const event = narrowTaskAgentEvent(value);
    onEvent(event);
    if (event.type === "completed" || event.type === "failed") terminal = event;
  };
  try {
    while (terminal === null) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) consumeLine(line);
    }
    if (terminal === null) consumeLine(buffer + decoder.decode());
  } finally {
    reader.releaseLock();
  }
  if (terminal === null) throw new TaskAgentStreamInterruptedError();
  return terminal;
}

/** `POST .../task-agent-turns` — one real task_agent turn, streamed (task
 *  058, N9): a `progress` line, the reply in `delta` pieces, then exactly one
 *  `completed` (the stored turn) or `failed`. `clientTurnId` is minted by the
 *  caller per logical turn (one per submitted message, not per send attempt)
 *  so that retrying the same submission reuses the id rather than minting a
 *  fresh one the server would treat as a new turn. A refusal before the
 *  stream opens (a fence, capacity) throws the server's envelope; a `failed`
 *  event throws its code; a dropped connection throws
 *  `TaskAgentStreamInterruptedError`. */
export function useTaskAgentTurn(taskId: string) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      message: string;
      clientTurnId: string;
      onEvent?: (event: TaskAgentStreamEvent) => void;
    }): Promise<components["schemas"]["TaskAgentTurnOut"]> => {
      const post = async (forceRefresh = false) => {
        const headers = await buildAuthHeaders(auth, forceRefresh);
        headers.set("Content-Type", "application/json");
        headers.set("Accept", "application/x-ndjson");
        return fetch(`${apiBaseUrl()}/api/v1/tasks/${taskId}/task-agent-turns`, {
          method: "POST",
          headers,
          body: JSON.stringify({ message: input.message, client_turn_id: input.clientTurnId }),
        });
      };
      let response = await post();
      if (response.status === 401) response = await post(true);
      if (!response.ok) {
        let envelope: unknown = undefined;
        try {
          envelope = await response.json();
        } catch {
          // Not a JSON body: `raise` falls back to a generic message.
        }
        raise(envelope, response.status);
      }
      if (response.body === null) throw new TaskAgentStreamInterruptedError();
      const terminal = await consumeTaskAgentStream(response.body, (event) => input.onEvent?.(event));
      if (terminal.type === "failed") raise({ error: terminal.error }, response.status);
      if (terminal.type !== "completed") throw new TaskAgentStreamInterruptedError();
      return terminal.turn;
    },
    // A dropped stream still lands a durable turn: re-read either way.
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.taskRoot(taskId) }),
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
    // Every start is a click: the moment the browser lets the page ask to alert when it finishes.
    onMutate: askForFinishAlerts,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.taskRoot(taskId) }),
  });
}

/** `POST .../plan/confirm-baseline` — record that a plan version was
 *  confirmed against its baseline (task 044, S4): a plan-scoped record, not a
 *  steering decision, so it works whether or not a walk is active for it to
 *  hang on. Idempotent on the same `(artefact_id, plan_version)` pair. */
export function useConfirmBaseline(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components["schemas"]["ConfirmBaselineIn"]) => {
      const { data, error, response } = await client.POST(
        "/api/v1/tasks/{task_id}/plan/confirm-baseline",
        {
          params: { path: { task_id: taskId } },
          body,
        },
      );
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.taskRoot(taskId) }),
  });
}

// --- Longlist (task 045 phase 6.2) --------------------------------------

/** Invalidate the longlist, every option card and the task itself (an add
 *  writes the header counts and can change `TaskOut.active_run`). */
function invalidateLonglist(queryClient: ReturnType<typeof useQueryClient>, taskId: string) {
  queryClient.invalidateQueries({ queryKey: [...queryKeys.taskRoot(taskId), "longlist"] });
  queryClient.invalidateQueries({ queryKey: [...queryKeys.taskRoot(taskId), "options"] });
  queryClient.invalidateQueries({ queryKey: queryKeys.task(taskId) });
}

/** `POST .../options` — add an option by hand (the button's path, same
 *  handler as the chat verb *add*): mints it *added by you* and opens its
 *  option search. */
export function useAddOption(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components["schemas"]["OptionAddIn"]) => {
      const { data, error, response } = await client.POST("/api/v1/tasks/{task_id}/options", {
        params: { path: { task_id: taskId } },
        body,
      });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => invalidateLonglist(queryClient, taskId),
  });
}

/** `POST .../options/{option_id}/exclude` (with the user's optional reason)
 *  or `.../include` (a rebuild's constrain will not exclude it again). Both
 *  return the option's card, written straight into its query. */
export function useOptionVerb(taskId: string, verb: "exclude" | "include") {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { optionId: string; reason?: string }) => {
      const { data, error, response } = await client.POST(
        `/api/v1/tasks/{task_id}/options/{option_id}/${verb}`,
        {
          params: { path: { task_id: taskId, option_id: input.optionId } },
          body: input.reason !== undefined ? { reason: input.reason } : null,
        },
      );
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: (data, input) => {
      queryClient.setQueryData([...queryKeys.taskRoot(taskId), "options", input.optionId], data);
      queryClient.invalidateQueries({ queryKey: [...queryKeys.taskRoot(taskId), "longlist"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.task(taskId) });
    },
  });
}

/** `POST .../options/{option_id}/shortlist` or `.../unshortlist` (no body):
 *  puts an option on the shortlist as added by you, or takes it off (a
 *  Policy Atlas pick becomes set aside). Returns the option's card, written
 *  straight into its query, like exclude and include. */
export function useShortlistVerb(taskId: string, verb: "shortlist" | "unshortlist") {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { optionId: string }) => {
      const { data, error, response } = await client.POST(`/api/v1/tasks/{task_id}/options/{option_id}/${verb}`, {
        params: { path: { task_id: taskId, option_id: input.optionId } },
      });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: (data, input) => {
      queryClient.setQueryData([...queryKeys.taskRoot(taskId), "options", input.optionId], data);
      invalidateLonglist(queryClient, taskId);
    },
  });
}

/** `POST .../shortlist/suggest` (no body, 202): opens a shortlist walk that
 *  fills the open places. Refused with 409 `run_active`, `capacity`,
 *  `plan_stale` or `nothing_to_propose`; the view words `plan_stale` with
 *  `suggestConflictSentences`. */
export function useSuggestMore(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await client.POST("/api/v1/tasks/{task_id}/shortlist/suggest", {
        params: { path: { task_id: taskId } },
      });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => {
      invalidateLonglist(queryClient, taskId);
      queryClient.invalidateQueries({ queryKey: queryKeys.taskRoot(taskId) });
    },
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

type Schemas = components["schemas"];

/** One edit to a theory of change (task 054, C41, C47, C40). */
export type TocEdit =
  | { kind: "createBox"; body: Schemas["TocBoxCreate"] }
  | { kind: "patchBox"; boxId: string; body: Schemas["TocBoxPatch"] }
  | { kind: "deleteBox"; boxId: string; revision: number }
  | { kind: "moveBox"; boxId: string; body: Schemas["TocMoveIn"] }
  | { kind: "resetLayout" }
  | { kind: "createLink"; body: Schemas["TocLinkCreate"] }
  | { kind: "patchLink"; linkId: string; body: Schemas["TocLinkPatch"] }
  | { kind: "deleteLink"; linkId: string; revision: number }
  | { kind: "undo"; eventId: string }
  | { kind: "check"; body: Schemas["TocCheckIn"] }
  | { kind: "evidence"; evidenceId: string; body: Schemas["TocEvidencePatch"] }
  | { kind: "keep"; body: Schemas["TocLinksIn"] }
  | { kind: "addStudy"; linkId: string; body: Schemas["TocStudyIn"] }
  | { kind: "decide"; linkId: string; accept: boolean }
  | { kind: "stop" }
  | { kind: "checkFull" }
  | { kind: "review" }
  | { kind: "proposal"; proposalId: string; body: Schemas["TocProposalDecideIn"] }
  | { kind: "dismiss"; proposalId: string }
  | { kind: "updateReport"; proposalId?: string };

/** The opening words of the message an upload sends (task 054, increment 5): its bubble shows the file. */
export const UPLOAD_MESSAGE = "I've uploaded my own theory of change";

/** The message an upload sends to start the planner: the file's name, then the user's note. */
export function uploadMessage(name: string, note: string): string {
  return `${UPLOAD_MESSAGE} (${name}).${note === "" ? "" : `\n\n${note}`}`;
}

/** Marks an upload in progress, so the chat finds it again after a tab switch. */
export const tocUploadKey = (taskId: string) => ["toc-upload", taskId] as const;

/**
 * `POST .../toc/uploads` — the user's own theory diagram (task 054, increment 5):
 * stored, then read by the model (about half a minute).
 * Upload the user's diagram, then send the message that starts the planner.
 * Both happen in one job, so they finish even if the chat closes meanwhile
 * (the user switches tab while the diagram is read).
 */
export function useTocUpload(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: tocUploadKey(taskId),
    mutationFn: async ({ file, note }: { file: File; note: string }) => {
      const type = file.type === "image/jpg" ? "image/jpeg" : file.type;
      if (type !== "image/png" && type !== "image/jpeg" && type !== "application/pdf") {
        throw new Error("Upload a PNG, JPEG or PDF file.");
      }
      if (file.size > 10 * 1024 * 1024) throw new Error("The file must be under 10 MB.");
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      const { data, error, response } = await client.POST("/api/v1/tasks/{task_id}/toc/uploads", {
        params: { path: { task_id: taskId } },
        body: { file_name: file.name, content_type: type, data_base64: dataUrl.slice(dataUrl.indexOf(",") + 1), message: uploadMessage(file.name, note) },
      });
      if (data === undefined) raise(error, response.status);
      // After the draft, the upload itself answers in the chat (its suggestions); before, the planner reads it.
      if (data.answered === true) return data;
      const turn = await client.POST("/api/v1/tasks/{task_id}/task-agent-turns", {
        params: { path: { task_id: taskId } },
        body: { message: uploadMessage(data.file_name, note), client_turn_id: crypto.randomUUID() },
      });
      if (turn.data === undefined) raise(turn.error, turn.response.status);
      return data;
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.taskRoot(taskId) }),
  });
}

/** The upload running for a task, if any: its file and note, whichever chat started it. */
export function useTocUploading(taskId: string): { file: File; note: string } | null {
  const running = useMutationState({
    filters: { mutationKey: tocUploadKey(taskId), status: "pending" },
    select: (mutation) => mutation.state.variables as { file: File; note: string },
  });
  return running.at(-1) ?? null;
}

/**
 * Every theory-of-change write, as one mutation. Each refreshes the graph,
 * its evidence and History (all under the task's `toc` key). A 409
 * `toc_stale_revision` reaches the caller as `error.code`.
 */
export function useTocEdit(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (edit: TocEdit) => {
      const task = { task_id: taskId };
      const done = ({ data, error, response }: { data?: unknown; error?: unknown; response: Response }) => {
        if (!response.ok) raise(error, response.status);
        return data;
      };
      switch (edit.kind) {
        case "createBox":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/boxes", { params: { path: task }, body: edit.body }));
        case "patchBox":
          return done(await client.PATCH("/api/v1/tasks/{task_id}/toc/boxes/{box_id}", { params: { path: { ...task, box_id: edit.boxId } }, body: edit.body }));
        case "deleteBox":
          return done(
            await client.DELETE("/api/v1/tasks/{task_id}/toc/boxes/{box_id}", { params: { path: { ...task, box_id: edit.boxId }, query: { expected_revision: edit.revision } } }),
          );
        case "moveBox":
          return done(await client.PATCH("/api/v1/tasks/{task_id}/toc/boxes/{box_id}/position", { params: { path: { ...task, box_id: edit.boxId } }, body: edit.body }));
        case "resetLayout":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/layout/reset", { params: { path: task } }));
        case "createLink":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/links", { params: { path: task }, body: edit.body }));
        case "patchLink":
          return done(await client.PATCH("/api/v1/tasks/{task_id}/toc/links/{link_id}", { params: { path: { ...task, link_id: edit.linkId } }, body: edit.body }));
        case "deleteLink":
          return done(
            await client.DELETE("/api/v1/tasks/{task_id}/toc/links/{link_id}", { params: { path: { ...task, link_id: edit.linkId }, query: { expected_revision: edit.revision } } }),
          );
        case "undo":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/events/{event_id}/undo", { params: { path: { ...task, event_id: edit.eventId } } }));
        case "check":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/check", { params: { path: task }, body: edit.body }));
        case "evidence":
          return done(await client.PATCH("/api/v1/tasks/{task_id}/toc/evidence/{evidence_id}", { params: { path: { ...task, evidence_id: edit.evidenceId } }, body: edit.body }));
        case "keep":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/links/keep", { params: { path: task }, body: edit.body }));
        case "decide":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/links/{link_id}/decide", { params: { path: { ...task, link_id: edit.linkId } }, body: { accept: edit.accept } }));
        case "review":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/review", { params: { path: task } }));
        case "proposal":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/proposals/{proposal_id}/decide", { params: { path: { ...task, proposal_id: edit.proposalId } }, body: edit.body }));
        case "dismiss":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/proposals/{proposal_id}/dismiss", { params: { path: { ...task, proposal_id: edit.proposalId } } }));
        case "updateReport":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/report/update", { params: { path: task, query: edit.proposalId !== undefined ? { proposal_id: edit.proposalId } : {} } }));
        case "stop":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/check/stop", { params: { path: task } }));
        case "checkFull":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/check/full", { params: { path: task } }));
        case "addStudy":
          return done(await client.POST("/api/v1/tasks/{task_id}/toc/links/{link_id}/studies", { params: { path: { ...task, link_id: edit.linkId } }, body: edit.body }));
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.toc(taskId) }),
  });
}
