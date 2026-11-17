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

export function useRequests() {
  const client = useOpsClient();
  return useQuery({ queryKey: REQUESTS, queryFn: () => unwrap(client.GET("/api/v1/ops/requests")) });
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
  organisations: readonly Organisation[],
): { tasks: number | null | undefined; runs: number | null | undefined } {
  const orgById = new Map(organisations.map((org) => [org.org_id, org]));
  const orgOf = (person: Person) =>
    person.organisation == null ? undefined : orgById.get(person.organisation.org_id);
  const tasks = people.find(
    (person) =>
      !person.is_admin &&
      person.task_quota_per_year == null &&
      orgOf(person)?.task_quota_per_year == null &&
      (person.organisation == null || orgOf(person) !== undefined),
  );
  // Administrators are exempt from both limits, so neither shows the default.
  const runs = people.find(
    (person) =>
      !person.is_admin &&
      person.runs_per_user == null &&
      orgOf(person)?.runs_per_user == null &&
      (person.organisation == null || orgOf(person) !== undefined),
  );
  return { tasks: tasks?.limits.task_quota_per_year, runs: runs?.limits.runs_per_user };
}
