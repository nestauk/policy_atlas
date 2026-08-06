import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../auth";
import { createAuthedApiClient } from "./client";

/**
 * Query-key roots, shared with `src/store/useRunStream.ts` so SSE-driven
 * invalidation can target "everything under this project" without every
 * hook here needing to know about the stream.
 */
export const queryKeys = {
  projectRoot: (projectId: string) => ["projects", projectId] as const,
  projects: (query?: { status?: "active" | "archived" | "all"; page?: number; page_size?: number }) =>
    ["projects", "list", query] as const,
  project: (projectId: string) => ["projects", projectId, "detail"] as const,
  checkIns: (projectId: string, status?: "pending" | "all") =>
    ["projects", projectId, "check-ins", status] as const,
  funnel: (projectId: string) => ["projects", projectId, "funnel"] as const,
  landscape: (projectId: string) => ["projects", projectId, "landscape"] as const,
  evidence: (projectId: string, query?: EvidenceQuery) =>
    ["projects", projectId, "evidence", query?.page, query?.page_size, query?.status, query?.cited] as const,
  findings: (projectId: string, query?: FindingsQuery) =>
    ["projects", projectId, "findings", query?.page, query?.page_size, query?.profile, query?.facet, query?.group, query?.group_id, query?.source_id] as const,
  decisions: (projectId: string, page?: number, pageSize?: number) =>
    ["projects", projectId, "decisions", page, pageSize] as const,
  planningTurns: (projectId: string, page?: number, pageSize?: number) =>
    ["projects", projectId, "planning-turns", page, pageSize] as const,
  plan: (projectId: string) => ["projects", projectId, "plan"] as const,
  runs: (projectId: string, page?: number, pageSize?: number) =>
    ["projects", projectId, "runs", page, pageSize] as const,
  artefact: (projectId: string) => ["projects", projectId, "artefact"] as const,
  sourceDossier: (projectId: string, sourceId: string) =>
    ["projects", projectId, "source-dossier", sourceId] as const,
};

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
}

export interface FindingsQuery extends PageQuery {
  profile?: "iof" | "icf";
  facet?: string;
  group?: string;
  group_id?: string;
  source_id?: string;
}

/** One authed `openapi-fetch` client per active `AuthApi` identity. */
export function useApiClient() {
  const auth = useAuth();
  return useMemo(() => createAuthedApiClient(auth), [auth]);
}

const ACTIVE_RUN_STATUSES = new Set(["running", "paused"]);

/** `GET /api/v1/projects` — paginated, owner-scoped. Live landing statuses
 *  (contract strand 14): while any listed project's `latest_run.status` is
 *  non-terminal, the list refetches on a modest interval so a card never
 *  keeps showing "Analysing"/"Paused" after the run has actually moved on.
 *  `refetchIntervalInBackground` defaults to `false`, so this only polls
 *  while the tab is visible. */
export function useProjects(query?: { status?: "active" | "archived" | "all"; page?: number; page_size?: number }) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.projects(query),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects", { params: { query } });
      if (error) throw error;
      return data;
    },
    refetchInterval: (activeQuery) => {
      const hasActiveRun = activeQuery.state.data?.data.some((project) =>
        project.latest_run !== null &&
        project.latest_run !== undefined &&
        ACTIVE_RUN_STATUSES.has(project.latest_run.status),
      );
      return hasActiveRun ? 15_000 : false;
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

/**
 * `GET /api/v1/projects/{project_id}/check-ins` — the derived pending card
 * (`status=pending`, the default) or the durable steering history
 * (`status=all`). `options.enabled`/`options.refetchInterval` let a caller
 * outside the workspace (the AppShell nav badge) poll cheaply for a pending
 * check-in without a live-run stream connection of its own.
 */
export function useCheckIns(
  projectId: string,
  status?: "pending" | "all",
  options?: { enabled?: boolean; refetchInterval?: number | false },
) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.checkIns(projectId, status),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/check-ins", {
        params: { path: { project_id: projectId }, query: { status } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId) && (options?.enabled ?? true),
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

/** `GET /api/v1/projects/{project_id}/funnel` — the durable
 *  acquisition-to-citation funnel, whole-object. */
export function useFunnel(projectId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.funnel(projectId),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/funnel", {
        params: { path: { project_id: projectId } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/projects/{project_id}/landscape` — screened-in-only
 *  distributions, whole-object. */
export function useLandscape(projectId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.landscape(projectId),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/landscape", {
        params: { path: { project_id: projectId } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/projects/{project_id}/evidence` — paginated source list
 *  with the status ladder. */
export function useEvidence(projectId: string, query?: EvidenceQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.evidence(projectId, query),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/evidence", {
        params: { path: { project_id: projectId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/projects/{project_id}/findings` — paginated IOF/ICF
 *  findings. */
export function useFindings(projectId: string, query?: FindingsQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.findings(projectId, query),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/findings", {
        params: { path: { project_id: projectId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/projects/{project_id}/sources/{source_id}` — one source's
 * provenance, latest citations and dossier detail. */
export function useSourceDossier(projectId: string, sourceId: string | null) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.sourceDossier(projectId, sourceId ?? ""),
    queryFn: async () => {
      if (!sourceId) return undefined;
      const { data, error } = await client.GET(
        "/api/v1/projects/{project_id}/sources/{source_id}",
        { params: { path: { project_id: projectId, source_id: sourceId } } },
      );
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId && sourceId),
  });
}

/** `GET /api/v1/projects/{project_id}/decisions` — paginated decision log
 *  (`steering_history` + allowlisted events). */
export function useDecisions(projectId: string, query?: PageQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.decisions(projectId, query?.page, query?.page_size),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/decisions", {
        params: { path: { project_id: projectId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/projects/{project_id}/planning-turns` — the durable,
 * paginated planning transcript in ascending `turn_index` order. */
export function usePlanningTurns(projectId: string, query?: PageQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.planningTurns(projectId, query?.page, query?.page_size),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/planning-turns", {
        params: { path: { project_id: projectId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET .../plan` — the approved plan or the latest durable draft. A 404 is a
 * normal pre-conversation state and resolves to `null`, never an error. */
export function usePlan(projectId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.plan(projectId),
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/v1/projects/{project_id}/plan",
        { params: { path: { project_id: projectId } } },
      );
      if (response.status === 404) return null;
      if (error) throw error;
      return data ?? null;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/projects/{project_id}/runs` — paginated run blocks for the
 * planning-thread composition model. */
export function useRuns(projectId: string, query?: PageQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.runs(projectId, query?.page, query?.page_size),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/runs", {
        params: { path: { project_id: projectId }, query },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/projects/{project_id}/artefact` — the latest persisted
 *  synthesis artefact (sections, span-anchored claims, citations), or a
 *  shaped absence, whole-object. */
export function useArtefact(projectId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.artefact(projectId),
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/v1/projects/{project_id}/artefact",
        { params: { path: { project_id: projectId } } },
      );
      // No artefact yet is a normal pre-synthesis state, not an error — a
      // thrown 404 here retries four times and holds a blank skeleton for
      // ~10s on a fresh project (owner feedback, 2026-07-29).
      if (response.status === 404) return null;
      if (error) throw error;
      return data ?? null;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/projects/{project_id}/coverage` — the composed one-line
 *  coverage sentence (stop condition + adequacy), carrying its base. */
export function useCoverage(projectId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: [...queryKeys.projectRoot(projectId), "coverage"] as const,
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/v1/projects/{project_id}/coverage",
        { params: { path: { project_id: projectId } } },
      );
      // No coverage record yet (nothing has run) is a normal state.
      if (response.status === 404) return null;
      if (error) throw error;
      return data ?? null;
    },
    enabled: Boolean(projectId),
  });
}

/** `GET /api/v1/projects/{project_id}/groups` — grouping facets. */
export function useGroups(projectId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: [...queryKeys.projectRoot(projectId), "groups"] as const,
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/groups", {
        params: { path: { project_id: projectId } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Boolean(projectId),
  });
}
