import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import createClient from "openapi-fetch";
import { useMemo } from "react";

import { createAuthMiddleware } from "../api/authMiddleware";
import type { components, paths } from "../api/gen/types-ops";
import { useAuth } from "../auth";
import type { AuthApi } from "../auth/types";

export type Person = components["schemas"]["PersonOut"];
export type Organisation = components["schemas"]["OrganisationOut"];
export type AccessRequest = components["schemas"]["RequestOut"];
export type Requests = components["schemas"]["RequestsOut"];
export type ActionResult = components["schemas"]["ActionResult"];
export type Cohort = components["schemas"]["CohortOut"];
export type CohortSave = components["schemas"]["CohortSave"];

/** A refused or failed ops call: the HTTP status (0 for no answer) and the
 *  error envelope's code and message. */
export class OpsApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/**
 * The ops pages' typed client (plan P2): always the page's own origin, which
 * serves `/api/v1/ops/*` too. It ignores `VITE_API_BASE_URL`, which points the
 * public app's build at the API host. The shared auth middleware adds the
 * bearer token and retries once after a silent refresh on a 401.
 */
export function createOpsApiClient(auth: AuthApi) {
  const client = createClient<paths>({ baseUrl: globalThis.location?.origin ?? "" });
  client.use(createAuthMiddleware(auth));
  return client;
}

export type OpsClient = ReturnType<typeof createOpsApiClient>;

function useOpsClient(): OpsClient {
  const auth = useAuth();
  return useMemo(() => createOpsApiClient(auth), [auth]);
}

/** Resolve an openapi-fetch call to its data, or throw `OpsApiError`. */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await call;
  } catch {
    throw new OpsApiError(0, "network", "");
  }
  if (!result.response.ok || result.data === undefined) {
    const body = result.error as { error?: { code?: string; message?: string } } | undefined;
    throw new OpsApiError(result.response.status, body?.error?.code ?? "", body?.error?.message ?? "");
  }
  return result.data;
}

/** The HTTP status behind a query or mutation error, or null. */
export function errorStatus(error: unknown): number | null {
  return error instanceof OpsApiError ? error.status : null;
}

const OPS = ["ops"] as const;
const PEOPLE = [...OPS, "people"] as const;
const ORGANISATIONS = [...OPS, "organisations"] as const;
const REQUESTS = [...OPS, "requests"] as const;
const COHORTS = [...OPS, "cohorts"] as const;

export function usePeople() {
  const client = useOpsClient();
  return useQuery({ queryKey: PEOPLE, queryFn: () => unwrap(client.GET("/api/v1/ops/people")) });
}

export function useOrganisations() {
  const client = useOpsClient();
  return useQuery({
    queryKey: ORGANISATIONS,
    queryFn: () => unwrap(client.GET("/api/v1/ops/organisations")),
  });
}

export function useCohorts() {
  const client = useOpsClient();
  return useQuery({ queryKey: COHORTS, queryFn: () => unwrap(client.GET("/api/v1/ops/cohorts")) });
}

/** Create a cohort (no id) or replace one's details. */
export function useSaveCohort() {
  return useOpsAction((client, { cohortId, body }: { cohortId: string | null; body: CohortSave }) =>
    cohortId === null
      ? unwrap(client.POST("/api/v1/ops/cohorts", { body }))
      : unwrap(client.POST("/api/v1/ops/cohorts/{cohort_id}", { params: { path: { cohort_id: cohortId } }, body })),
  );
}

export function useCohortQuota(cohortId: string) {
  return useOpsAction((client, body: QuotaValues) =>
    unwrap(
      client.POST("/api/v1/ops/cohorts/{cohort_id}/quota", { params: { path: { cohort_id: cohortId } }, body }),
    ),
  );
}

export function useDeleteCohort() {
  return useOpsAction(async (client, cohortId: string) => {
    const { response } = await client.DELETE("/api/v1/ops/cohorts/{cohort_id}", {
      params: { path: { cohort_id: cohortId } },
    });
    if (!response.ok) throw new OpsApiError(response.status, "", "");
  });
}

/** Add the people to a cohort, or take them out of it. */
export function useCohortMembers(path: "/api/v1/ops/people/cohort-add" | "/api/v1/ops/people/cohort-remove") {
  return useOpsAction((client, body: { user_ids: string[]; cohort_id: string }) => unwrap(client.POST(path, { body })));
}

/** The waitlist; with `rejected`, the rejected requests too (kept as a record). */
export function useRequests(rejected = false) {
  const client = useOpsClient();
  return useQuery({
    queryKey: [...REQUESTS, { rejected }],
    queryFn: () => unwrap(client.GET("/api/v1/ops/requests", { params: { query: { rejected } } })),
  });
}

/**
 * One ops write. Every write may change every list (a move changes an
 * organisation's count, an approval adds a person), so each one refreshes
 * them all.
 */
export function useOpsAction<V, R>(run: (client: OpsClient, variables: V) => Promise<R>) {
  const client = useOpsClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (variables: V) => run(client, variables),
    onSettled: () => queryClient.invalidateQueries({ queryKey: OPS }),
  });
}

/** The bulk routes that take only the subjects. */
export type BulkPath =
  | "/api/v1/ops/people/de-enrol"
  | "/api/v1/ops/people/offboard"
  | "/api/v1/ops/people/resend";

export function useBulk(path: BulkPath) {
  return useOpsAction((client, userIds: string[]) =>
    unwrap(client.POST(path, { body: { user_ids: userIds } })),
  );
}

export function useEnrol() {
  return useOpsAction((client, body: { user_ids: string[]; org_id: string }) =>
    unwrap(client.POST("/api/v1/ops/people/enrol", { body })),
  );
}

/** A quota form's two fields: a number, or null to inherit. */
export interface QuotaValues {
  task_quota_per_year: number | null;
  runs_per_user: number | null;
}

export function usePeopleQuota() {
  return useOpsAction((client, body: QuotaValues & { user_ids: string[] }) =>
    unwrap(client.POST("/api/v1/ops/people/quota", { body })),
  );
}

export function useOrganisationQuota(orgId: string) {
  return useOpsAction((client, body: QuotaValues) =>
    unwrap(
      client.POST("/api/v1/ops/organisations/{org_id}/quota", {
        params: { path: { org_id: orgId } },
        body,
      }),
    ),
  );
}

/**
 * The settings defaults, which no route reports directly: the limits of a
 * person with no override of their own and none from their organisation
 * and who is not an administrator (exempt from both).
 * `undefined` when no such person is listed.
 */
export function inferDefaults(
  people: readonly Person[],
): { tasks: number | null | undefined; runs: number | null | undefined } {
  const tasks = people.find((person) => person.limits.task_quota_from === "the default");
  const runs = people.find((person) => person.limits.runs_from === "the default");
  return { tasks: tasks?.limits.task_quota_per_year, runs: runs?.limits.runs_per_user };
}
