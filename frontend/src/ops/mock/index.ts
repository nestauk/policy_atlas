import type { AuthApi } from "../../auth/types";
import type { ActionResult, Cohort, ImportProblem, ImportRow, InviteLink, Organisation, Person, Requests } from "../api";
import {
  cohortFixtures,
  inviteLinkFixtures,
  OPS_ME,
  organisationFixtures,
  peopleFixtures,
  requestFixtures,
} from "./fixtures";

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
  inviteLinks: InviteLink[];
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
  inviteLinks: [],
  writes: [],
};

/** Put the fixtures back and forget overrides and writes. */
export function resetOpsMock() {
  opsMock.people = peopleFixtures();
  opsMock.organisations = organisationFixtures();
  opsMock.cohorts = cohortFixtures();
  opsMock.requests = requestFixtures();
  opsMock.inviteLinks = inviteLinkFixtures();
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

const DAY_MS = 24 * 60 * 60 * 1000;

/** A link's state, worked out when read, as the server does. */
function linkState(link: InviteLink): InviteLink["state"] {
  if (link.revoked_at != null) return "revoked";
  if (Date.parse(link.expires_at) <= Date.now()) return "expired";
  return link.uses >= link.max_uses ? "full" : "active";
}

/** The limits' refusal; a value not sent (an edit's) is not checked. */
function limitsRefusal(maxUses: number | undefined, expiresAt: string | undefined): string | null {
  if (maxUses !== undefined && !(maxUses >= 1 && maxUses <= 1000)) return "Maximum uses must be from 1 to 1,000.";
  const end = expiresAt === undefined ? undefined : Date.parse(expiresAt);
  if (end !== undefined && !(end > Date.now() && end <= Date.now() + 91 * DAY_MS)) {
    return "Choose a date in the next 90 days.";
  }
  return null;
}

function domainsRefusal(domains: string[]): string | null {
  if (domains.length === 0) return "Enter at least one domain.";
  if (domains.length > 10) return "A link can have at most 10 domains.";
  const bad = domains.findIndex((domain) => !/^[a-z0-9-]+(\.[a-z0-9-]+)+$/i.test(domain));
  if (bad >= 0) return `Line ${bad + 1}: enter a domain such as dhsc.gov.uk, with no @.`;
  const lower = domains.map((domain) => domain.toLowerCase());
  return new Set(lower).size < lower.length ? "This domain is on the list twice." : null;
}

/** One CSV line's values: commas split, double quotes hold commas. */
function csvValues(line: string): string[] {
  return [...line.matchAll(/(?:^|,)("(?:[^"]|"")*"|[^,]*)/g)].map((match) =>
    match[1].startsWith('"') ? match[1].slice(1, -1).replace(/""/g, '"') : match[1].trim(),
  );
}

/** The file check, roughly as the server does it: enough for the pages' states. */
function checkPeopleFile(csv: string): { rows: ImportRow[]; errors: ImportProblem[] } {
  if (csv.includes(String.fromCharCode(0xfffd))) {
    return { rows: [], errors: [{ line: null, message: "This file is not saved as UTF-8. Save it as CSV UTF-8 and choose it again." }] };
  }
  const lines = csv.replace(new RegExp(`^${String.fromCharCode(0xfeff)}`), "").split(/\r?\n/);
  const header = csvValues(lines[0] ?? "").map((value) => value.toLowerCase());
  const emailAt = header.indexOf("email");
  const nameAt = header.indexOf("name");
  if (emailAt < 0 || nameAt < 0 || header.length !== 2) {
    return { rows: [], errors: [{ line: null, message: "The file needs the columns email and name." }] };
  }
  const rows: ImportRow[] = [];
  const errors: ImportProblem[] = [];
  const seen = new Map<string, number>();
  lines.slice(1).forEach((text, index) => {
    const line = index + 2;
    if (text.trim() === "") return;
    const values = csvValues(text);
    const email = (values[emailAt] ?? "").toLowerCase();
    const name = values[nameAt] ?? "";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) errors.push({ line, message: "this is not an email address." });
    else if (seen.has(email)) errors.push({ line, message: `this email is already on line ${seen.get(email)}.` });
    else if (name === "") errors.push({ line, message: "a name is required." });
    else rows.push({ line, email, display_name: name });
    if (!seen.has(email)) seen.set(email, line);
  });
  if (rows.length + errors.length > 500) errors.push({ line: null, message: "A file can hold at most 500 people." });
  return { rows, errors };
}

function route(method: string, path: string, body: Record<string, unknown>, query = new URLSearchParams()): Response {
  const ids = (body.user_ids as string[] | undefined) ?? [];
  const now = new Date().toISOString();

  if (method === "GET" && path === "/api/v1/ops/people") return json(opsMock.people);
  if (method === "GET" && path === "/api/v1/ops/organisations") return json(opsMock.organisations);
  if (method === "GET" && path === "/api/v1/ops/requests") {
    // Like the server: only requests still waiting for a decision, and the
    // rejected ones when asked.
    const rejected = query.get("rejected") === "true";
    return json({
      ...opsMock.requests,
      items: opsMock.requests.items.filter(
        (item) => item.status !== "invited" && (rejected || item.status !== "rejected"),
      ),
    });
  }
  const rejectPath = /^\/api\/v1\/ops\/requests\/([^/]+)\/reject$/.exec(path);
  if (rejectPath !== null && method === "POST") {
    const target = opsMock.requests.items.find((item) => item.entry_id === rejectPath[1]);
    if (target === undefined) return apiError(404, "not_found", "resource not found");
    target.status = "rejected";
    target.rejected_at = now;
    return new Response(null, { status: 204 });
  }
  if (method === "GET" && path === "/api/v1/ops/cohorts") return json(opsMock.cohorts);

  const cohortQuota = /^\/api\/v1\/ops\/cohorts\/([^/]+)\/quota$/.exec(path);
  if (cohortQuota !== null && method === "POST") {
    const target = opsMock.cohorts.find((entry) => entry.cohort_id === cohortQuota[1]);
    if (target === undefined) return apiError(404, "not_found", "resource not found");
    target.task_quota_per_year = (body.task_quota_per_year as number | null) ?? null;
    target.runs_per_user = (body.runs_per_user as number | null) ?? null;
    return json(target);
  }

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
    const cohorts = ((body.cohort_ids as string[] | undefined) ?? []).map((id) =>
      opsMock.cohorts.find((entry) => entry.cohort_id === id),
    );
    if (cohorts.some((cohort) => cohort === undefined)) return apiError(404, "not_found", "resource not found");
    const join = (subject: Person) => {
      for (const cohort of cohorts as Cohort[]) {
        if (subject.cohorts.some((own) => own.cohort_id === cohort.cohort_id)) continue;
        subject.cohorts = [...subject.cohorts, { cohort_id: cohort.cohort_id, name: cohort.name }];
        cohort.people += 1;
      }
    };
    if (existing?.deactivated_at != null) {
      // A file run sends `reactivate: false` and is refused; the one-person form turns them back on.
      if (body.reactivate === false) {
        return apiError(409, "deactivated", `${email} is deactivated. Nothing was written. Reactivate them on People first.`);
      }
      existing.deactivated_at = null;
      existing.organisation = org;
      join(existing);
      return json({ person: existing, invitation_sent: false, reactivated: true }, 201);
    }
    if (existing !== undefined) {
      existing.organisation = org;
      join(existing);
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
      limits: { task_quota_per_year: 50, runs_per_user: 3, task_quota_from: { kind: "default" }, runs_from: { kind: "default" } },
      cohorts: [],
    };
    join(created);
    opsMock.people.push(created);
    return json({ person: created, invitation_sent: true }, 201);
  }
  if (method === "POST" && path === "/api/v1/ops/people/import-check") return json(checkPeopleFile(String(body.csv)));

  if (method === "GET" && path === "/api/v1/ops/invite-links") {
    return json(opsMock.inviteLinks.map((link) => ({ ...link, state: linkState(link) })));
  }
  if (method === "POST" && path === "/api/v1/ops/invite-links") {
    const refusal =
      domainsRefusal(body.allowed_domains as string[]) ??
      limitsRefusal(Number(body.max_uses), String(body.expires_at));
    if (refusal !== null) return apiError(409, "ops_refused", refusal);
    const org = orgRef(String(body.org_id));
    if (org === undefined) return apiError(404, "not_found", "resource not found");
    const code = "K7Q2-M9XD-3FHP";
    const created: InviteLink = {
      invite_link_id: newId(),
      label: String(body.label),
      organisation: org,
      cohorts: ((body.cohort_ids as string[] | undefined) ?? []).flatMap((id) =>
        opsMock.cohorts.filter((entry) => entry.cohort_id === id).map(({ cohort_id, name }) => ({ cohort_id, name })),
      ),
      allowed_domains: (body.allowed_domains as string[]).map((domain) => domain.toLowerCase()),
      max_uses: Number(body.max_uses),
      uses: 0,
      expires_at: String(body.expires_at),
      revoked_at: null,
      created_at: now,
      state: "active",
      url: `https://policy-atlas.example/#invite=${code}`,
    };
    opsMock.inviteLinks.push(created);
    return json(created, 201);
  }
  const linkPath = /^\/api\/v1\/ops\/invite-links\/([^/]+)(\/revoke)?$/.exec(path);
  if (method === "POST" && linkPath !== null) {
    const link = opsMock.inviteLinks.find((entry) => entry.invite_link_id === linkPath[1]);
    if (link === undefined) return apiError(404, "not_found", "resource not found");
    if (link.revoked_at != null) return apiError(409, "ops_refused", "A revoked link cannot be changed.");
    if (linkPath[2] !== undefined) {
      link.revoked_at = now;
    } else {
      // As the route: only the values sent change; a body with none is refused.
      const label = body.label == null ? undefined : String(body.label);
      const maxUses = body.max_uses == null ? undefined : Number(body.max_uses);
      const expiresAt = body.expires_at == null ? undefined : String(body.expires_at);
      if (label === undefined && maxUses === undefined && expiresAt === undefined) {
        return apiError(422, "validation_error", "send at least one of label, max_uses, expires_at");
      }
      const refusal =
        maxUses !== undefined && maxUses < link.uses
          ? `This link already has ${link.uses} uses. The maximum cannot be lower.`
          : limitsRefusal(maxUses, expiresAt);
      if (refusal !== null) return apiError(409, "ops_refused", refusal);
      Object.assign(link, {
        label: label ?? link.label,
        max_uses: maxUses ?? link.max_uses,
        expires_at: expiresAt ?? link.expires_at,
      });
    }
    return json({ ...link, state: linkState(link) });
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
  if (method === "POST" && path === "/api/v1/ops/people/deactivate") {
    return bulk(ids, (subject) => {
      subject.deactivated_at = subject.deactivated_at ?? now;
      subject.is_admin = false;
      subject.is_ops = false;
      return "ok";
    });
  }
  if (method === "POST" && path === "/api/v1/ops/people/reactivate") {
    return bulk(ids, (subject) => {
      subject.deactivated_at = null;
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
  const orgPath = /^\/api\/v1\/ops\/organisations\/([^/]+)$/.exec(path);
  if (method === "DELETE" && orgPath !== null) {
    const org = opsMock.organisations.find((entry) => entry.org_id === orgPath[1]);
    if (org === undefined) return apiError(404, "not_found", "resource not found");
    const people = opsMock.people.filter((entry) => entry.organisation?.org_id === org.org_id).length;
    // As the server: a revoked link nobody used goes with the organisation.
    const links = opsMock.inviteLinks.filter(
      (link) => link.organisation.org_id === org.org_id && (link.revoked_at == null || link.uses > 0),
    ).length;
    const left = (
      [
        [people, "person", "people"],
        [org.domains.length, "domain", "domains"],
        [links, "invite link", "invite links"],
      ] as const
    ).flatMap(([count, one, many]) => (count > 0 ? [`${count} ${count === 1 ? one : many}`] : []));
    if (left.length > 0) {
      const listed = left.length === 1 ? left[0] : `${left.slice(0, -1).join(", ")} and ${left.at(-1)}`;
      return apiError(409, "ops_refused", `${org.name} still has ${listed}. Nothing was deleted.`);
    }
    opsMock.organisations = opsMock.organisations.filter((entry) => entry !== org);
    return new Response(null, { status: 204 });
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
    entry.rejected_at = null;
    return json(entry);
  }
  const requestPath = /^\/api\/v1\/ops\/requests\/([^/]+)$/.exec(path);
  if (method === "DELETE" && requestPath !== null) {
    const entry = opsMock.requests.items.find((item) => item.entry_id === requestPath[1]);
    if (entry === undefined) return apiError(404, "not_found", "resource not found");
    if (entry.status !== "rejected") return apiError(409, "ops_refused", "only a rejected request can be deleted");
    opsMock.requests.items = opsMock.requests.items.filter((item) => item !== entry);
    return new Response(null, { status: 204 });
  }

  return apiError(404, "not_found", "resource not found");
}

/** Answer one ops request from memory. */
export async function opsMockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const request = input instanceof Request ? input : new Request(input, init);
  const url = new URL(request.url);
  const path = url.pathname;
  const text = request.method === "GET" ? "" : await request.clone().text();
  const body = (text === "" ? {} : JSON.parse(text)) as Record<string, unknown>;
  if (request.method !== "GET") opsMock.writes.push({ method: request.method, path, body });
  return opsMock.override?.(request.method, path, body) ?? route(request.method, path, body, url.searchParams);
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
