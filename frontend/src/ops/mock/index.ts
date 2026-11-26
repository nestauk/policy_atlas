import type { AuthApi } from "../../auth/types";
import type {
  ActionResult,
  AnnouncementDetail,
  AnnouncementKind,
  Audience,
  Cohort,
  Organisation,
  Person,
  RecipientPreview,
  Requests,
} from "../api";
import {
  cohortFixtures,
  exampleAudience,
  LATE_UNSUBSCRIBER,
  NESTA,
  OPS_ME,
  organisationFixtures,
  peopleFixtures,
  requestFixtures,
  RESUBSCRIBER,
  SPRING,
  TOMAS,
  type ExamplePerson,
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
  /** The people the announcement routes choose from (the annex's 82). */
  example: ExamplePerson[];
  /** Sent announcements, newest first, as the detail route answers them (counts are worked out on reading). */
  announcements: Array<Omit<AnnouncementDetail, "counts" | "suppression_unreadable">>;
  /**
   * The 409 `recipients_changed` trigger: when true, the next send finds
   * the list changed (Kwame Osei subscribes again and one other Nesta person
   * unsubscribes, so a product update to Nesta still reaches the same number
   * of people) and answers 409 once. Off after a reset; a test sets it, and
   * `?mock=list-changes` in the address sets it in the browser.
   */
  listChangesOnNextSend: boolean;
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
  example: [],
  announcements: [],
  listChangesOnNextSend: false,
  writes: [],
};

/** Put the fixtures back and forget overrides and writes. */
export function resetOpsMock() {
  opsMock.people = peopleFixtures();
  opsMock.organisations = organisationFixtures();
  opsMock.cohorts = cohortFixtures();
  opsMock.requests = requestFixtures();
  opsMock.example = exampleAudience();
  opsMock.announcements = announcementFixtures();
  opsMock.listChangesOnNextSend = false;
  opsMock.override = undefined;
  opsMock.writes = [];
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function apiError(status: number, code: string, message: string, details?: unknown): Response {
  return json({ error: { code, message, ...(details !== undefined && { details }) } }, status);
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

/* Announcements: the recipient rules, the record and the routes, in memory. */

type Stored = OpsMockState["announcements"][number];
type Reason = NonNullable<RecipientPreview["recipients"][number]["reason"]>;

/** Like the server: the first reason that applies, or null when the person gets the email. */
function leftOutReason(
  person: { deactivated: boolean; email: string | null; signedIn: boolean; unsubscribed: boolean },
  kind: AnnouncementKind,
): Reason | null {
  if (person.deactivated) return "deactivated";
  if (person.email == null) return "no_email";
  if (kind === "product_update" && !person.signedIn) return "not_signed_in";
  if (kind === "product_update" && person.unsubscribed) return "unsubscribed";
  return null;
}

/** A short stand-in for the server's SHA-256 over the list. */
function fingerprint(lines: string[]): string {
  let hash = 0;
  for (const char of lines.join("\n")) hash = (Math.imul(hash, 31) + char.charCodeAt(0)) | 0;
  return `fp-${(hash >>> 0).toString(16)}`;
}

/**
 * The recipients route's answer: the example people the audience names,
 * and any person from the People list chosen by name.
 */
function preview(kind: AnnouncementKind, audience: Audience): RecipientPreview {
  const cohorts = audience.cohort_ids ?? [];
  const orgs = audience.org_ids ?? [];
  const users = audience.user_ids ?? [];
  const candidates = opsMock.example
    .filter(
      (person) =>
        audience.everyone ||
        (person.spring && cohorts.includes(SPRING)) ||
        (person.nesta && orgs.includes(NESTA)) ||
        users.includes(person.user_id),
    )
    .map((person) => ({ ...person, signedIn: true as boolean, email: person.email as string | null }));
  for (const userId of users) {
    const own = opsMock.people.find((entry) => entry.user_id === userId);
    if (own === undefined || candidates.some((person) => person.user_id === userId)) continue;
    candidates.push({
      user_id: own.user_id,
      name: own.display_name,
      email: own.email ?? null,
      organisation: own.organisation?.name ?? "",
      spring: false,
      nesta: false,
      deactivated: own.deactivated_at != null,
      unsubscribed: false,
      signedIn: own.first_signed_in_at != null,
    });
  }
  const recipients = candidates
    .map((person) => {
      const reason = leftOutReason(person, kind);
      return {
        user_id: person.user_id,
        name: person.name,
        email: person.email,
        organisation: person.organisation || null,
        status: reason === null ? ("pending" as const) : ("left_out" as const),
        reason,
      };
    })
    .sort((a, b) => a.user_id.localeCompare(b.user_id));
  const leftOut: Record<string, number> = {};
  for (const person of recipients) if (person.reason !== null) leftOut[person.reason] = (leftOut[person.reason] ?? 0) + 1;
  return {
    chosen: recipients.length,
    will_get: recipients.filter((person) => person.status === "pending").length,
    left_out: leftOut,
    recipients,
    fingerprint: fingerprint(recipients.map((p) => `${p.user_id}|${p.email ?? ""}|${p.status}|${p.reason ?? ""}`)),
  };
}

/** The audience in words, as the server writes it: "Everyone", or the names and "N people". */
function audienceSummary(audience: Audience): string {
  if (audience.everyone) return "Everyone";
  const parts = [
    ...(audience.cohort_ids ?? []).map((id) => opsMock.cohorts.find((entry) => entry.cohort_id === id)?.name ?? id),
    ...(audience.org_ids ?? []).map((id) => opsMock.organisations.find((entry) => entry.org_id === id)?.name ?? id),
  ];
  const people = new Set(audience.user_ids ?? []).size;
  if (people > 0) parts.push(`${people} ${people === 1 ? "person" : "people"}`);
  return parts.join(", ");
}

/** The field rules the server applies to a message, as its 422 `invalid_message` answer naming the field. */
function messageRule(body: Record<string, unknown>): Response | null {
  const text = (key: string) => (typeof body[key] === "string" ? (body[key] as string) : "");
  const broken = (field: string, message: string) => apiError(422, "invalid_message", message, { field });
  if (text("subject").trim() === "") return broken("subject", "the subject is empty");
  if (text("body").trim() === "") return broken("body", "the message is empty");
  if ((text("button_label") === "") !== (text("button_url") === "")) {
    return broken("button_label", "a button needs both its words and its link");
  }
  if (text("button_url") !== "" && !text("button_url").startsWith("https://")) {
    return broken("button_url", "the button link must start with https://");
  }
  if ((text("image_url") === "") !== (text("image_alt") === "")) {
    return broken("image_alt", "a picture needs both its address and its description");
  }
  return null;
}

/** A sent announcement as stored: every recipient sent, but `failed` people, with the code the mail service gave. */
function sentAnnouncement(
  fields: Pick<Stored, "subject" | "kind" | "body" | "button_label" | "button_url" | "image_url" | "image_alt">,
  audience: Audience,
  sentBy: string,
  createdAt: string,
  failed: Record<string, string> = {},
): Stored {
  const built = preview(fields.kind, audience);
  return {
    ...fields,
    announcement_id: newId(),
    audience_summary: audienceSummary(audience),
    sent_by_name: sentBy,
    created_at: createdAt,
    recipients: built.recipients
      .map((person) => {
        const code = failed[person.user_id];
        return person.status === "left_out"
          ? { ...person, overlay: null }
          : { ...person, status: code === undefined ? ("sent" as const) : ("failed" as const), reason: code ?? null, overlay: null };
      })
      .sort((a, b) => a.name.localeCompare(b.name)),
  };
}

const EXAMPLE_AUDIENCE: Audience = { everyone: false, cohort_ids: [SPRING], org_ids: [NESTA], user_ids: [TOMAS] };

/** The two people whose email the mail service turns down on every send, with its code. */
const FAILED_RECIPIENTS: Record<string, string> = { "sub-imogen": "MessageRejected", "sub-dev": "Throttling" };

/** The signed-in ops person's display name, as the server stores it on a send. */
const myName = () => opsMock.people.find((person) => person.user_id === OPS_ME)?.display_name ?? "";

/** The list's three sent announcements (the annex's scene 1), newest first. */
function announcementFixtures(): Stored[] {
  const day = 24 * 60 * 60 * 1000;
  const iso = (msAgo: number) => new Date(Date.now() - msAgo).toISOString();
  const me = myName();
  const none = { button_label: null, button_url: null, image_url: null, image_alt: null };
  return [
    sentAnnouncement(
      {
        subject: "What's new: theory of change maps",
        kind: "product_update",
        body:
          "You can now build a theory of change in Policy Atlas.\n\n" +
          "- Start from a short description, or import a picture of a map you already have\n" +
          "- Check each link in the map against the evidence\n" +
          "- Download the map to edit it in draw.io\n\n" +
          "Reply to this email if you have questions.",
        button_label: "Open Policy Atlas",
        button_url: "https://policyatlas.example",
        image_url: "https://policyatlas.example/email-images/theory-of-change.png",
        image_alt: "A theory of change map with five linked boxes",
      },
      EXAMPLE_AUDIENCE,
      me,
      iso(2 * day),
      FAILED_RECIPIENTS,
    ),
    sentAnnouncement(
      { subject: "Your pilot starts on Monday", kind: "service_notice", body: "Your pilot starts on Monday.", ...none },
      { everyone: false, cohort_ids: [SPRING], org_ids: [], user_ids: [] },
      "Ana Ruiz",
      iso(13 * day),
    ),
    sentAnnouncement(
      {
        subject: "Sign-in now needs an authenticator app",
        kind: "service_notice",
        body: "From Monday, signing in needs an authenticator app.",
        ...none,
      },
      { everyone: true, cohort_ids: [], org_ids: [], user_ids: [] },
      me,
      iso(17 * day),
    ),
  ];
}

function withCounts(stored: Stored): AnnouncementDetail {
  const counts = { pending: 0, sending: 0, sent: 0, failed: 0, left_out: 0 };
  for (const person of stored.recipients) counts[person.status] += 1;
  return { ...stored, counts, suppression_unreadable: false };
}

function announcementRoute(method: string, path: string, body: Record<string, unknown>): Response | undefined {
  if (method === "GET" && path === "/api/v1/ops/announcements") {
    return json({
      items: opsMock.announcements.map((stored) => {
        const { announcement_id, subject, kind, audience_summary, sent_by_name, created_at, counts } = withCounts(stored);
        return { announcement_id, subject, kind, audience_summary, sent_by_name, created_at, counts };
      }),
    });
  }
  if (method === "POST" && path === "/api/v1/ops/announcements/recipients") {
    return json(preview(body.kind as AnnouncementKind, body.audience as Audience));
  }
  if (method === "POST" && path === "/api/v1/ops/announcements/test") {
    return messageRule(body) ?? new Response(null, { status: 204 });
  }
  if (method === "POST" && path === "/api/v1/ops/announcement-images") {
    const data = String(body.data_base64 ?? "");
    if ((data.length * 3) / 4 > 1024 * 1024) return apiError(422, "upload_size", "The picture must be under 1 MB.");
    const suffix = body.content_type === "image/png" ? "png" : "jpg";
    return json({ url: `https://policyatlas.example/email-images/${newId()}.${suffix}` }, 201);
  }
  if (method === "POST" && path === "/api/v1/ops/announcements") {
    const kind = body.kind as AnnouncementKind;
    const audience = body.audience as Audience;
    const rule = messageRule(body);
    if (rule !== null) return rule;
    if (opsMock.listChangesOnNextSend) {
      opsMock.listChangesOnNextSend = false;
      for (const person of opsMock.example) {
        if (person.user_id === RESUBSCRIBER) person.unsubscribed = false;
        if (person.user_id === LATE_UNSUBSCRIBER) person.unsubscribed = true;
      }
    }
    const now = preview(kind, audience);
    if (now.fingerprint !== body.fingerprint) {
      return apiError(409, "recipients_changed", "the list of recipients changed", now);
    }
    const text = (key: string) => (typeof body[key] === "string" && body[key] !== "" ? (body[key] as string) : null);
    const stored = sentAnnouncement(
      {
        subject: String(body.subject),
        kind,
        body: String(body.body),
        button_label: text("button_label"),
        button_url: text("button_url"),
        image_url: text("image_url"),
        image_alt: text("image_alt"),
      },
      audience,
      myName(),
      new Date().toISOString(),
      FAILED_RECIPIENTS,
    );
    opsMock.announcements = [stored, ...opsMock.announcements];
    return json({ announcement_id: stored.announcement_id }, 201);
  }
  const one = /^\/api\/v1\/ops\/announcements\/([^/]+)(\/retry)?$/.exec(path);
  if (one !== null) {
    const stored = opsMock.announcements.find((entry) => entry.announcement_id === one[1]);
    if (stored === undefined) return apiError(404, "not_found", "resource not found");
    if (method === "GET" && one[2] === undefined) return json(withCounts(stored));
    if (method === "POST" && one[2] !== undefined) {
      // The retry sends the failed rows again; here they go through at once.
      stored.recipients = stored.recipients.map((person) =>
        person.status === "failed" ? { ...person, status: "sent" as const, reason: null } : person,
      );
      return new Response(null, { status: 202 });
    }
  }
  return undefined;
}

function route(method: string, path: string, body: Record<string, unknown>, query = new URLSearchParams()): Response {
  const announcement = announcementRoute(method, path, body);
  if (announcement !== undefined) return announcement;
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
      limits: { task_quota_per_year: 50, runs_per_user: 3, task_quota_from: { kind: "default" }, runs_from: { kind: "default" } },
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
    const left = [people && `${people} people`, org.domains.length && `${org.domains.length} domains`].filter(Boolean);
    if (left.length > 0) {
      return apiError(409, "ops_refused", `${org.name} still has ${left.join(", ")}. Nothing was deleted.`);
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
 * role sees, or `?mock=list-changes` to have the first announcement sent
 * find its list changed (the confirm dialog's 409).
 */
export function installOpsMock() {
  resetOpsMock();
  const mock = new URLSearchParams(window.location.search).get("mock");
  if (mock === "forbidden") {
    opsMock.override = () => apiError(403, "forbidden", "your account does not have the ops role");
  }
  opsMock.listChangesOnNextSend = mock === "list-changes";
  (globalThis as typeof globalThis & { __policyAtlasMockAuth?: AuthApi }).__policyAtlasMockAuth = mockOpsAuth;
  const realFetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), window.location.origin);
    return url.pathname.startsWith("/api/v1/ops/") ? opsMockFetch(input, init) : realFetch(input, init);
  }) as typeof fetch;
}
