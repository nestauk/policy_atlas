import type { AuthApi } from "../../auth/types";
import type { ActionResult, Cohort, Organisation, Person, Requests } from "../api";
import { cohortFixtures, OPS_ME, organisationFixtures, peopleFixtures, requestFixtures } from "./fixtures";

/*
 * The ops routes in memory, for `VITE_MOCK=1` and the vitest tests. Like the
 * product's `src/mock/api.ts`, it answers at `fetch`, so the pages' own
 * client, middleware and error handling run unchanged. A test can replace
 * one answer with `opsMock.override`.
 */

interface OpsMockState {
  people: Person[];
  organisations: Organisation[];
  cohorts: Cohort[];
  requests: Requests;
  /** Answer before the in-memory routes; return undefined to fall through. */
  override?: (method: string, path: string, body: unknown) => Response | undefined;
  /** Every write the pages sent, in order. */
  writes: Array<{ method: string; path: string; body: unknown }>;
}

export const opsMock: OpsMockState = {
  people: [],
  organisations: [],
  cohorts: [],
  requests: requestFixtures(),
  writes: [],
};

/** Put the fixtures back and forget overrides and writes. */
export function resetOpsMock() {
  opsMock.people = peopleFixtures();
  opsMock.organisations = organisationFixtures();
  opsMock.cohorts = cohortFixtures();
  opsMock.requests = requestFixtures();
  opsMock.override = undefined;
  opsMock.writes = [];
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function apiError(status: number, code: string, message: string): Response {
  return json({ error: { code, message } }, status);
}

let nextId = 1;
const newId = () => `00000000-0000-4000-8000-${String(nextId++).padStart(12, "0")}`;

function person(userId: string): Person | undefined {
  return opsMock.people.find((entry) => entry.user_id === userId);
}

function orgRef(orgId: string) {
  const org = opsMock.organisations.find((entry) => entry.org_id === orgId);
  return org === undefined ? undefined : { org_id: org.org_id, name: org.name };
}

function bulk(ids: string[], run: (subject: Person) => ActionResult["outcome"] | string) {
  return json({
    results: ids.map((userId): ActionResult => {
      const subject = person(userId);
      if (subject === undefined) {
        return { user_id: userId, outcome: "failed", message: `no person ${userId}`, action_id: newId() };
      }
      const outcome = run(subject);
      if (outcome === "too_soon") {
        return { user_id: userId, outcome, message: "an invitation was sent recently", action_id: null };
      }
      if (outcome !== "ok") return { user_id: userId, outcome: "failed", message: outcome, action_id: newId() };
      return { user_id: userId, outcome: "ok", message: `done for ${subject.email ?? userId}`, action_id: newId() };
    }),
  });
}

function route(method: string, path: string, body: Record<string, unknown>): Response {
  const ids = (body.user_ids as string[] | undefined) ?? [];
  const now = new Date().toISOString();

  if (method === "GET" && path === "/api/v1/ops/people") return json(opsMock.people);
  if (method === "GET" && path === "/api/v1/ops/organisations") return json(opsMock.organisations);
  if (method === "GET" && path === "/api/v1/ops/requests") return json(opsMock.requests);
  if (method === "GET" && path === "/api/v1/ops/cohorts") return json(opsMock.cohorts);

  const cohortPath = /^\/api\/v1\/ops\/cohorts(?:\/([^/]+))?$/.exec(path);
  if (cohortPath !== null && method === "POST") {
    const name = String(body.name).trim();
    const id = cohortPath[1];
    if (opsMock.cohorts.some((entry) => entry.name.toLowerCase() === name.toLowerCase() && entry.cohort_id !== id)) {
      return apiError(409, "ops_refused", `a cohort named '${name}' already exists`);
    }
    const existing = opsMock.cohorts.find((entry) => entry.cohort_id === id);
    if (id !== undefined && existing === undefined) return apiError(404, "not_found", "resource not found");
    const saved: Cohort = {
      cohort_id: id ?? newId(),
      created_at: existing?.created_at ?? now,
      people: existing?.people ?? 0,
      name,
      description: (body.description as string | null) ?? null,
      starts_on: (body.starts_on as string | null) ?? null,
      ends_on: (body.ends_on as string | null) ?? null,
      links: (body.links as string[] | undefined) ?? [],
    };
    opsMock.cohorts = [...opsMock.cohorts.filter((entry) => entry.cohort_id !== saved.cohort_id), saved].sort((a, b) =>
      a.name.localeCompare(b.name),
    );
    for (const subject of opsMock.people) {
      subject.cohorts = subject.cohorts.map((own) => (own.cohort_id === saved.cohort_id ? { cohort_id: own.cohort_id, name } : own));
    }
    return json(saved, id === undefined ? 201 : 200);
  }
  if (cohortPath !== null && method === "DELETE" && cohortPath[1] !== undefined) {
    const id = cohortPath[1];
    if (!opsMock.cohorts.some((entry) => entry.cohort_id === id)) return apiError(404, "not_found", "resource not found");
    opsMock.cohorts = opsMock.cohorts.filter((entry) => entry.cohort_id !== id);
    for (const subject of opsMock.people) subject.cohorts = subject.cohorts.filter((own) => own.cohort_id !== id);
    return new Response(null, { status: 204 });
  }
  if (method === "POST" && (path === "/api/v1/ops/people/cohort-add" || path === "/api/v1/ops/people/cohort-remove")) {
    const target = opsMock.cohorts.find((entry) => entry.cohort_id === body.cohort_id);
    if (target === undefined) return apiError(404, "not_found", "resource not found");
    const adding = path.endsWith("cohort-add");
    const response = bulk(ids, (subject) => {
      const inIt = subject.cohorts.some((own) => own.cohort_id === target.cohort_id);
      if (adding && !inIt) subject.cohorts = [...subject.cohorts, { cohort_id: target.cohort_id, name: target.name }];
      if (!adding) subject.cohorts = subject.cohorts.filter((own) => own.cohort_id !== target.cohort_id);
      return "ok";
    });
    target.people = opsMock.people.filter((subject) => subject.cohorts.some((own) => own.cohort_id === target.cohort_id)).length;
    return response;
  }

  if (method === "POST" && path === "/api/v1/ops/people") {
    const email = String(body.email).toLowerCase();
    const existing = opsMock.people.find((entry) => entry.email === email);
    const org = orgRef(String(body.org_id));
    if (org === undefined) return apiError(404, "not_found", "resource not found");
    if (existing?.organisation != null && existing.organisation.org_id !== org.org_id) {
      return apiError(
        409,
        "enrolled_elsewhere",
        `${email} is already in ${existing.organisation.name}. Nothing was written. Move them from the People list (\`user enrol\`).`,
      );
    }
    if (existing !== undefined) {
      existing.organisation = org;
      return json({ person: existing, invitation_sent: false }, 201);
    }
    const created: Person = {
      user_id: `sub-${newId()}`,
      display_name: String(body.display_name),
      email,
      organisation: org,
      is_admin: false,
      is_ops: false,
      created_at: now,
      invited_at: now,
      task_quota_per_year: null,
      runs_per_user: null,
      tasks_this_year: 0,
      limits: { task_quota_per_year: 50, runs_per_user: 3 },
      cohorts: [],
    };
    opsMock.people.push(created);
    return json({ person: created, invitation_sent: true }, 201);
  }

  if (method === "POST" && path === "/api/v1/ops/people/enrol") {
    const org = orgRef(String(body.org_id));
    return bulk(ids, (subject) => {
      subject.organisation = org;
      return "ok";
    });
  }
  if (method === "POST" && path === "/api/v1/ops/people/de-enrol") {
    return bulk(ids, (subject) => {
      subject.organisation = null;
      subject.is_admin = false;
      subject.is_ops = false;
      return "ok";
    });
  }
  if (method === "POST" && path === "/api/v1/ops/people/offboard") {
    return bulk(ids, (subject) => {
      opsMock.people = opsMock.people.filter((entry) => entry !== subject);
      return "ok";
    });
  }
  if (method === "POST" && path === "/api/v1/ops/people/resend") {
    const cooling = (subject: Person | undefined) =>
      subject?.invited_at != null && Date.now() - Date.parse(subject.invited_at) < 3600_000;
    // As the route does: every subject cooling down is a 429, not a list of skips.
    if (ids.every((userId) => cooling(person(userId)))) {
      return apiError(429, "resend_cooldown", "an invitation was sent recently");
    }
    return bulk(ids, (subject) => {
      if (cooling(subject)) return "too_soon";
      if (subject.email == null) return "no address to send to";
      subject.invited_at = now;
      return "ok";
    });
  }
  if (method === "POST" && path === "/api/v1/ops/people/quota") {
    return bulk(ids, (subject) => {
      subject.task_quota_per_year = (body.task_quota_per_year as number | null) ?? null;
      subject.runs_per_user = (body.runs_per_user as number | null) ?? null;
      return "ok";
    });
  }

  if (method === "POST" && path === "/api/v1/ops/organisations") {
    const name = String(body.name).trim();
    if (opsMock.organisations.some((org) => org.name.toLowerCase() === name.toLowerCase())) {
      return apiError(409, "ops_refused", `an organisation named '${name}' already exists`);
    }
    const created: Organisation = {
      org_id: newId(),
      name,
      created_at: now,
      people: 0,
      task_quota_per_year: null,
      runs_per_user: null,
      domains: [],
    };
    opsMock.organisations.push(created);
    return json(created, 201);
  }
  const quota = /^\/api\/v1\/ops\/organisations\/([^/]+)\/quota$/.exec(path);
  if (method === "POST" && quota !== null) {
    const org = opsMock.organisations.find((entry) => entry.org_id === quota[1]);
    if (org === undefined) return apiError(404, "not_found", "resource not found");
    org.task_quota_per_year = (body.task_quota_per_year as number | null) ?? null;
    org.runs_per_user = (body.runs_per_user as number | null) ?? null;
    return json(org);
  }

  const approve = /^\/api\/v1\/ops\/requests\/([^/]+)\/approve$/.exec(path);
  if (method === "POST" && approve !== null) {
    const entry = opsMock.requests.items.find((item) => item.entry_id === approve[1]);
    const org = orgRef(String(body.org_id));
    if (entry === undefined || org === undefined) return apiError(404, "not_found", "resource not found");
    entry.status = "invited";
    entry.account_created_at = now;
    return json(entry);
  }

  return apiError(404, "not_found", "resource not found");
}

/** Answer one ops request from memory. */
export async function opsMockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const request = input instanceof Request ? input : new Request(input, init);
  const path = new URL(request.url).pathname;
  const text = request.method === "GET" ? "" : await request.clone().text();
  const body = (text === "" ? {} : JSON.parse(text)) as Record<string, unknown>;
  if (request.method !== "GET") opsMock.writes.push({ method: request.method, path, body });
  return opsMock.override?.(request.method, path, body) ?? route(request.method, path, body);
}

/** A signed-in ops person, for the mock and the tests. */
export const mockOpsAuth: AuthApi = {
  getAccessToken: async () => "mock-ops-token",
  signIn: () => undefined,
  signOut: () => undefined,
  onUnauthenticated: () => undefined,
  user: { sub: OPS_ME },
  status: "authenticated",
};

/**
 * Answer `/api/v1/ops/*` from memory in the browser (`VITE_MOCK=1`). Add
 * `?mock=forbidden` to the address to see the page a person without the ops
 * role sees.
 */
export function installOpsMock() {
  resetOpsMock();
  if (new URLSearchParams(window.location.search).get("mock") === "forbidden") {
    opsMock.override = () => apiError(403, "forbidden", "your account does not have the ops role");
  }
  (globalThis as typeof globalThis & { __policyAtlasMockAuth?: AuthApi }).__policyAtlasMockAuth = mockOpsAuth;
  const realFetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), window.location.origin);
    return url.pathname.startsWith("/api/v1/ops/") ? opsMockFetch(input, init) : realFetch(input, init);
  }) as typeof fetch;
}
