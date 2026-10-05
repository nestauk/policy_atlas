import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../auth";
import { createAuthedApiClient } from "./client";
import type { components } from "./gen/types";

/**
 * Query-key roots, shared with `src/store/useRunStream.tsx` so SSE-driven
 * invalidation can target "everything under this task" without every
 * hook here needing to know about the stream.
 */
export const queryKeys = {
  me: () => ["me"] as const,
  taskRoot: (taskId: string) => ["tasks", taskId] as const,
  // `scope` and `project_id` are embedded via the whole `query` object, so
  // they participate in the key automatically (task 033 phase 10a) — every
  // distinct filter combination, including the switcher's future `scope`,
  // gets its own cache entry rather than silently serving another scope's
  // rows.
  tasks: (query?: TasksQuery) => ["tasks", "list", query] as const,
  task: (taskId: string) => ["tasks", taskId, "detail"] as const,
  checkIns: (taskId: string, status?: "pending" | "all") =>
    ["tasks", taskId, "check-ins", status] as const,
  funnel: (taskId: string) => ["tasks", taskId, "funnel"] as const,
  landscape: (taskId: string, scope?: "cited") =>
    ["tasks", taskId, "landscape", scope] as const,
  evidence: (taskId: string, query?: EvidenceQuery) =>
    ["tasks", taskId, "evidence", query?.page, query?.page_size, query?.status, query?.cited, query?.sort, query?.order, query?.theme, query?.origin, query?.evidence_type, query?.strength, query?.year_from, query?.year_to] as const,
  findings: (taskId: string, query?: FindingsQuery) =>
    ["tasks", taskId, "findings", query?.page, query?.page_size, query?.profile, query?.facet, query?.group, query?.group_id, query?.source_id] as const,
  decisions: (taskId: string, page?: number, pageSize?: number) =>
    ["tasks", taskId, "decisions", page, pageSize] as const,
  planningTurns: (taskId: string, page?: number, pageSize?: number) =>
    ["tasks", taskId, "planning-turns", page, pageSize] as const,
  plan: (taskId: string) => ["tasks", taskId, "plan"] as const,
  runs: (taskId: string, page?: number, pageSize?: number) =>
    ["tasks", taskId, "runs", page, pageSize] as const,
  artefact: (taskId: string) => ["tasks", taskId, "artefact"] as const,
  sourceDossier: (taskId: string, sourceId: string) =>
    ["tasks", taskId, "source-dossier", sourceId] as const,
  /** Prefix shared by every filtered variant below — invalidate with this,
   *  not the filtered key, so a mutation clears every consumer's cache
   *  regardless of which `kind`/`status` it queried with (partial match
   *  requires the invalidated key to be an actual prefix of the stored one). */
  conversationsRoot: (taskId: string) => ["tasks", taskId, "conversations"] as const,
  conversations: (taskId: string, query?: ConversationQuery) =>
    [...queryKeys.conversationsRoot(taskId), query?.kind, query?.status] as const,
  conversation: (conversationId: string) => ["conversations", conversationId, "detail"] as const,
  chatTurns: (conversationId: string) => ["conversations", conversationId, "turns"] as const,
  // Same whole-object embedding as `tasks` above, so `scope` differs the
  // key without a separate positional argument.
  projects: (query?: ProjectsQuery) => ["projects", "list", query] as const,
  project: (projectId: string) => ["projects", projectId, "detail"] as const,
};

/** `GET /api/v1/tasks` filters (task 033 phase 10a adds `scope` and
 *  `project_id`). `scope` defaults server-side to `all`; the frontend
 *  passes it explicitly only where a caller needs something other than that
 *  default (the phase 10b switcher), so day-one behaviour is unchanged. */
interface TasksQuery {
  status?: "active" | "archived" | "all";
  scope?: "all" | "mine";
  project_id?: string | null;
  page?: number;
  page_size?: number;
}

/** `GET /api/v1/projects` filters (task 033 phase 10a adds `scope`). */
interface ProjectsQuery {
  scope?: "all" | "mine";
  page?: number;
  page_size?: number;
}

/** Shared shape for the paginated read models (`evidence`, `findings`,
 *  `decisions`) — server page-size cap is 200, default 50 (web-api.md
 *  § Pagination). */
interface PageQuery {
  page?: number;
  page_size?: number;
}

type EvidenceStatusFilter =
  | "found"
  | "screened_out"
  | "relevant"
  | "not_selected"
  | "selected"
  | "read_in_full"
  | "findings_extracted"
  | "cited"
  | "unavailable"
  | "Included";

export interface EvidenceQuery extends PageQuery {
  status?: EvidenceStatusFilter[];
  cited?: boolean;
  /** Server-side sort key (default unsorted); `order` is 422 without it. */
  sort?: "title" | "year" | "type" | "strength" | "status" | "relevance";
  order?: "asc" | "desc";
  /** Theme id (`ThemeOut.theme_id`) — collection-true across pages. */
  theme?: string;
  origin?: "OpenAlex" | "Overton" | "Uploaded";
  evidence_type?: string;
  strength?: "Very strong" | "Strong" | "Moderate" | "Limited" | "Weak";
  year_from?: number;
  year_to?: number;
}

interface FindingsQuery extends PageQuery {
  profile?: "iof" | "icf";
  facet?: string;
  group?: string;
  group_id?: string;
  source_id?: string;
}

/** Filters for the task conversation library. */
interface ConversationQuery {
  kind?: "planning" | "chat";
  status?: "active" | "closed" | "archived";
}

/** One authed `openapi-fetch` client per active `AuthApi` identity. */
export function useApiClient() {
  const auth = useAuth();
  return useMemo(() => createAuthedApiClient(auth), [auth]);
}

/**
 * `GET /api/v1/me` — the caller's own identity row (task 033), provisioned
 * on first call. Keys the whole tenancy UI: a `null` `organisation` hides
 * the scope switcher and every org-scoped affordance.
 *
 * `staleTime: Infinity` is deliberate: the row changes only via an ops
 * action (enrol/de-enrol, admin grant/revoke) — never something this app
 * writes — so there is no in-session event that should invalidate it, and
 * paying for a refetch on every navigation would buy nothing. The only path
 * an ops change reaches an open session is a fresh load anyway, which starts
 * a fresh `QueryClient` and re-fetches for free.
 */
export function useMe() {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.me(),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/me");
      if (error) throw error;
      return data;
    },
    staleTime: Infinity,
  });
}

const ACTIVE_RUN_STATUSES = new Set(["running", "paused"]);

/** `GET /api/v1/tasks` — paginated, owner-scoped. Live landing statuses
 *  (contract strand 14): while any listed task's `latest_run.status` is
 *  non-terminal, the list refetches on a modest interval so a card never
 *  keeps showing "Analysing"/"Paused" after the run has actually moved on.
 *  `refetchIntervalInBackground` defaults to `false`, so this only polls
 *  while the tab is visible. */
export function useTasks(query?: TasksQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.tasks(query),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks", { params: { query } });
      if (error) throw error;
      return data;
    },
    refetchInterval: (activeQuery) => {
      const hasActiveRun = activeQuery.state.data?.data.some((task) =>
        task.latest_run !== null &&
        task.latest_run !== undefined &&
        ACTIVE_RUN_STATUSES.has(task.latest_run.status),
      );
      return hasActiveRun ? 15_000 : false;
    },
  });
}

/** `GET /api/v1/projects` — the screen's Projects, with a derived task count. */
export function useProjects(query?: ProjectsQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.projects(query),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects", { params: { query } });
      if (error) throw error;
      return data;
    },
  });
}

/** `GET /api/v1/projects/{project_id}`. */
export function useProject(projectId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}", {
        params: { path: { project_id: projectId } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/tasks/{task_id}`.
 *
 *  `options.pollWhileRunning` keeps `latest_run.status` fresh for a caller
 *  with no run stream of its own — historically the app shell's lifecycle
 *  locking. The shell now also owns `RunStreamProvider`, which invalidates
 *  this query on `stage.completed` / `run.status`; polling remains as a
 *  reconnect-gap belt-and-braces. */
export function useTask(taskId: string, options?: { pollWhileRunning?: boolean }) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.task(taskId),
    queryFn: async () => {
      const { data, error, response } = await client.GET("/api/v1/tasks/{task_id}", {
        params: { path: { task_id: taskId } },
      });
      if (error) throw Object.assign(new Error("Failed to load task"), { status: response.status });
      return data;
    },
    enabled: Boolean(taskId),
    // A 4xx (an anonymous 404 on a private/unknown Task, task 037) means the
    // same thing on every attempt — retrying it just holds the caller
    // (PublicTaskShell's stash-and-splash fallback) for ~7s across the
    // default 3 retries before landing where it was always going to land.
    // Retry only a network failure (no `status`) or a server error, up to
    // the default cap.
    retry: (failureCount, error) => {
      const status = (error as { status?: number }).status;
      if (status !== undefined && status < 500) return false;
      return failureCount < 3;
    },
    refetchInterval: (activeQuery) => {
      if (options?.pollWhileRunning !== true) return false;
      const status = activeQuery.state.data?.latest_run?.status;
      return status !== undefined && ACTIVE_RUN_STATUSES.has(status) ? 15_000 : false;
    },
  });
}

/**
 * `GET /api/v1/tasks/{task_id}/check-ins` — the derived pending card
 * (`status=pending`, the default) or the durable steering history
 * (`status=all`). `options.enabled`/`options.refetchInterval` let a caller
 * outside the workspace (the AppShell nav badge) poll cheaply for a pending
 * check-in without a live-run stream connection of its own.
 */
export function useCheckIns(
  taskId: string,
  status?: "pending" | "all",
  options?: { enabled?: boolean; refetchInterval?: number | false },
) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.checkIns(taskId, status),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/check-ins", {
        params: { path: { task_id: taskId }, query: { status } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId) && (options?.enabled ?? true),
    refetchInterval: options?.refetchInterval,
  });
}

// --- Read-model hooks (task 025 §6) -----------------------------------
//
// These resources landed in the generated contract mid-build (a backend
// slice building `policy_atlas.api.readmodels` concurrently with this
// one) — `gen/types.ts` now exposes `funnel`/`landscape`/`evidence`/
// `findings`/`decisions`/`artefact` alongside `groups`/`coverage` (the
// latter two aren't named in the task brief's hook list and are left for
// whichever view first needs them). Each hook below is typed straight off
// the generated `paths`, so if the backend's read-model logic still 404s
// in practice, that's an ordinary query error surfaced through
// `useQuery`'s `error` — not a typecheck-time concern.

/** `GET /api/v1/tasks/{task_id}/funnel` — the durable
 *  acquisition-to-citation funnel, whole-object. */
export function useFunnel(taskId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.funnel(taskId),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/funnel", {
        params: { path: { task_id: taskId } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/landscape` — screened-in-only
 *  distributions, whole-object. */
export function useLandscape(taskId: string, scope?: "cited") {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.landscape(taskId, scope),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/landscape", {
        params: { path: { task_id: taskId }, query: scope !== undefined ? { scope } : undefined },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/evidence` — paginated source list
 *  with the status ladder. */
export function useEvidence(taskId: string, query?: EvidenceQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.evidence(taskId, query),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/evidence", {
        params: { path: { task_id: taskId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/findings` — paginated IOF/ICF
 *  findings. */
export function useFindings(taskId: string, query?: FindingsQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.findings(taskId, query),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/findings", {
        params: { path: { task_id: taskId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/sources/{source_id}` — one source's
 * provenance, latest citations and dossier detail. */
export function useSourceDossier(taskId: string, sourceId: string | null) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.sourceDossier(taskId, sourceId ?? ""),
    queryFn: async () => {
      if (!sourceId) return undefined;
      const { data, error } = await client.GET(
        "/api/v1/tasks/{task_id}/sources/{source_id}",
        { params: { path: { task_id: taskId, source_id: sourceId } } },
      );
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId && sourceId),
  });
}

/** `GET /api/v1/tasks/{task_id}/decisions` — paginated decision log
 *  (`steering_history` + allowlisted events). */
export function useDecisions(taskId: string, query?: PageQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.decisions(taskId, query?.page, query?.page_size),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/decisions", {
        params: { path: { task_id: taskId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/planning-turns` — the durable,
 * paginated planning transcript in ascending `turn_index` order. */
export function usePlanningTurns(taskId: string, query?: PageQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.planningTurns(taskId, query?.page, query?.page_size),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/planning-turns", {
        params: { path: { task_id: taskId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/conversations` — the task chat and
 * planning-conversation library. `options.enabled` lets the public task view
 * (task 037) keep the hook mounted without issuing the non-public request. */
export function useConversations(
  taskId: string,
  query?: ConversationQuery,
  options?: { enabled?: boolean },
) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.conversations(taskId, query),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/conversations", {
        params: { path: { task_id: taskId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId) && (options?.enabled ?? true),
  });
}

/** `GET /api/v1/conversations/{conversation_id}` — one URL-addressable
 * conversation's durable metadata. */
export function useConversation(conversationId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.conversation(conversationId),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/conversations/{conversation_id}", {
        params: { path: { conversation_id: conversationId } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(conversationId),
  });
}

/** Server page-size cap for `.../turns` (`PAGE_SIZE_MAX`, `contract/common.py`) —
 *  requesting it directly means a chat past the 50-row default page still
 *  fetches its newest turns in one extra round trip at most. */
const CHAT_TURNS_PAGE_SIZE = 200;

/** `GET /api/v1/conversations/{conversation_id}/turns` — a chat's durable
 *  ascending turn transcript, fully paginated: the server only ever returns
 *  one page (default 50 rows), so a chat past that length silently lost its
 *  newest turns until this loop walked every page and accumulated them. The
 *  enrichment poll's find-by-id (`store/conversations.ts`) reads this same
 *  query, so it inherits the fix for free. */
export function useChatTurns(conversationId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.chatTurns(conversationId),
    queryFn: async () => {
      const turns: components["schemas"]["ChatTurnOut"][] = [];
      let page = 1;
      let pagination: components["schemas"]["PageMeta"] | undefined;
      for (;;) {
        const { data, error } = await client.GET("/api/v1/conversations/{conversation_id}/turns", {
          params: { path: { conversation_id: conversationId }, query: { page, page_size: CHAT_TURNS_PAGE_SIZE } },
        });
        if (error) throw error;
        turns.push(...data.data);
        pagination = data.pagination;
        if (data.data.length < CHAT_TURNS_PAGE_SIZE || turns.length >= data.pagination.total_items) break;
        page += 1;
      }
      return { data: turns, pagination: pagination! };
    },
    enabled: Boolean(conversationId),
  });
}

/** `GET .../plan` — the approved plan or the latest durable draft. A 404 is a
 * normal pre-conversation state and resolves to `null`, never an error. */
export function usePlan(taskId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.plan(taskId),
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/v1/tasks/{task_id}/plan",
        { params: { path: { task_id: taskId } } },
      );
      if (response.status === 404) return null;
      if (error) throw error;
      return data ?? null;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/runs` — paginated run blocks for the
 * planning-thread composition model. */
export function useRuns(taskId: string, query?: PageQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs(taskId, query?.page, query?.page_size),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/runs", {
        params: { path: { task_id: taskId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/artefact` — the latest persisted
 *  synthesis artefact (sections, span-anchored claims, citations), or a
 *  shaped absence, whole-object. */
export function useArtefact(taskId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.artefact(taskId),
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/v1/tasks/{task_id}/artefact",
        { params: { path: { task_id: taskId } } },
      );
      // No artefact yet is a normal pre-synthesis state, not an error — a
      // thrown 404 here retries four times and holds a blank skeleton for
      // ~10s on a fresh task (owner feedback, 2026-07-29).
      if (response.status === 404) return null;
      if (error) throw error;
      return data ?? null;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/coverage` — the composed one-line
 *  coverage sentence (stop condition + adequacy), carrying its base. */
export function useCoverage(taskId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: [...queryKeys.taskRoot(taskId), "coverage"] as const,
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/v1/tasks/{task_id}/coverage",
        { params: { path: { task_id: taskId } } },
      );
      // No coverage record yet (nothing has run) is a normal state.
      if (response.status === 404) return null;
      if (error) throw error;
      return data ?? null;
    },
    enabled: Boolean(taskId),
  });
}

/** `GET /api/v1/tasks/{task_id}/groups` — grouping facets. */
export function useGroups(taskId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: [...queryKeys.taskRoot(taskId), "groups"] as const,
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/tasks/{task_id}/groups", {
        params: { path: { task_id: taskId } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(taskId),
  });
}
