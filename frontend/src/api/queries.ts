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
  evidence: (projectId: string, page?: number, pageSize?: number) =>
    ["projects", projectId, "evidence", page, pageSize] as const,
  findings: (projectId: string, page?: number, pageSize?: number) =>
    ["projects", projectId, "findings", page, pageSize] as const,
  decisions: (projectId: string, page?: number, pageSize?: number) =>
    ["projects", projectId, "decisions", page, pageSize] as const,
  artefact: (projectId: string) => ["projects", projectId, "artefact"] as const,
};

/** Shared shape for the paginated read models (`evidence`, `findings`,
 *  `decisions`) — server page-size cap is 200, default 50 (web-api.md
 *  § Pagination). */
interface PageQuery {
  page?: number;
  page_size?: number;
}

/** One authed `openapi-fetch` client per active `AuthApi` identity. */
export function useApiClient() {
  const auth = useAuth();
  return useMemo(() => createAuthedApiClient(auth), [auth]);
}

/** `GET /api/v1/projects` — paginated, owner-scoped. */
export function useProjects(query?: { status?: "active" | "archived" | "all"; page?: number; page_size?: number }) {
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

/**
 * `GET /api/v1/projects/{project_id}/check-ins` — the derived pending card
 * (`status=pending`, the default) or the durable steering history
 * (`status=all`).
 */
export function useCheckIns(projectId: string, status?: "pending" | "all") {
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
    enabled: Boolean(projectId),
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
export function useEvidence(projectId: string, query?: PageQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.evidence(projectId, query?.page, query?.page_size),
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
export function useFindings(projectId: string, query?: PageQuery) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.findings(projectId, query?.page, query?.page_size),
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

/** `GET /api/v1/projects/{project_id}/artefact` — the latest persisted
 *  synthesis artefact (sections, span-anchored claims, citations), or a
 *  shaped absence, whole-object. */
export function useArtefact(projectId: string) {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.artefact(projectId),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/artefact", {
        params: { path: { project_id: projectId } },
      });
      if (error) throw error;
      return data;
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
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/coverage", {
        params: { path: { project_id: projectId } },
      });
      if (error) throw error;
      return data;
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
