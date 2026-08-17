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

/** `POST /api/v1/projects` — create a project. */
export function useCreateProject() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; question?: string | null }) => {
      const { data, error, response } = await client.POST("/api/v1/projects", { body });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
}

/** `PATCH .../{id}` — partial update (rename and/or question edit). */
export function useUpdateProject(projectId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name?: string | null; question?: string | null }) => {
      const { data, error, response } = await client.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: projectId } },
        body,
      });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    // The bare "projects" root covers BOTH this project's detail key and the
    // projects-list key (["projects", "list", …]) — a rename must refresh the
    // landing card, not just the workspace header (F.2 finding, 2026-07-29).
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
}

/** `POST .../archive` — idempotent soft-delete (409 `run_active` while running). */
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
}

/** `POST .../planning-turns` — one real planner turn. `clientTurnId` is
 *  minted by the caller per logical turn (one per submitted message, not
 *  per send attempt) so that retrying the same submission reuses the id
 *  rather than minting a fresh one the server would treat as a new turn. */
export function usePlanningTurn(projectId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { message: string; clientTurnId: string }) => {
      const { data, error, response } = await client.POST(
        "/api/v1/projects/{project_id}/planning-turns",
        {
          params: { path: { project_id: projectId } },
          body: { message: input.message, client_turn_id: input.clientTurnId },
        },
      );
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.projectRoot(projectId) }),
  });
}

/** `POST .../runs` — dispatch the approved plan's walk (409 while one is active). */
export function useStartRun(projectId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await client.POST("/api/v1/projects/{project_id}/runs", {
        params: { path: { project_id: projectId } },
        body: {},
      });
      if (data === undefined) raise(error, response.status);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.projectRoot(projectId) }),
  });
}

/** `POST .../check-ins/{id}/response` — option/abort answers and the free-text
 *  compile→confirm ladder (202 carries the compiled render + confirm token). */
export function useAnswerCheckIn(projectId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { checkInId: string; body: CheckInResponseBody }) => {
      const { data, error, response } = await client.POST(
        "/api/v1/projects/{project_id}/check-ins/{check_in_id}/response",
        {
          params: { path: { project_id: projectId, check_in_id: input.checkInId } },
          body: input.body,
        },
      );
      if (response.status === 202 && data !== undefined) {
        return { kind: "compiled" as const, compiled: data };
      }
      if (!response.ok) raise(error, response.status);
      return { kind: "answered" as const };
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.projectRoot(projectId) }),
  });
}

/** `PATCH .../sources/{id}` — set or clear the human "not relevant" flag.
 *  Feedback only: the flag never moves the source on the evidence status
 *  ladder. Idempotent in both directions, so a double-click is harmless. */
export function useSetSourceNotRelevant(projectId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { sourceId: string; notRelevant: boolean }) => {
      const { data, error, response } = await client.PATCH(
        "/api/v1/projects/{project_id}/sources/{source_id}",
        {
          params: { path: { project_id: projectId, source_id: input.sourceId } },
          body: { not_relevant: input.notRelevant },
        },
      );
      if (data === undefined) raise(error, response.status);
      return data;
    },
    // The project root is a prefix of both queryKeys.evidence(...) and
    // queryKeys.sourceDossier(...), so one invalidate refreshes the table row
    // and an open dossier together.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.projectRoot(projectId) }),
  });
}

/** `POST .../issue-reports` — free-text issue report. No LLM, and nothing
 *  reads these back in-app, so there is no cache to invalidate. */
export function useReportIssue(projectId: string) {
  const client = useApiClient();
  return useMutation({
    mutationFn: async (input: { body: string; pagePath?: string }) => {
      const { data, error, response } = await client.POST(
        "/api/v1/projects/{project_id}/issue-reports",
        {
          params: { path: { project_id: projectId } },
          body: { body: input.body, page_path: input.pagePath ?? null },
        },
      );
      if (data === undefined) raise(error, response.status);
      return data;
    },
  });
}
