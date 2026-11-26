import type { AccessRequest, Cohort, InviteLink, Organisation, Person, Requests } from "../api";

/*
 * The ops mock's fixtures: people with every flag and invitation time the
 * People page shows, requests in the three states, organisations with and
 * without domains and overrides. Times are relative to the moment they are
 * made, so the resend cooldown and "2 h ago" read the same on any day.
 */

export const OPS_ME = "sub-ops-priya";
export const NESTA = "00000000-0000-4000-8000-00000000000a";
export const POLICY_LAB = "00000000-0000-4000-8000-00000000000b";
export const EMPTY_ORG = "00000000-0000-4000-8000-00000000000c";
export const PANEL = "00000000-0000-4000-8000-00000000000d";
export const PILOT = "00000000-0000-4000-8000-00000000000e";
export const DHSC = "00000000-0000-4000-8000-00000000000f";
export const DHSC_PILOT = "00000000-0000-4000-8000-000000000010";
export const LINK_ACTIVE = "00000000-0000-4000-8000-0000000000a1";

const MINUTE = 60 * 1000;
const iso = (msAgo: number) => new Date(Date.now() - msAgo).toISOString();

export function organisationFixtures(): Organisation[] {
  return [
    {
      org_id: NESTA,
      name: "Nesta",
      created_at: iso(200 * 24 * 60 * MINUTE),
      people: 4,
      task_quota_per_year: 100,
      runs_per_user: null,
      domains: ["nesta.org.uk"],
    },
    {
      org_id: POLICY_LAB,
      name: "Policy Lab",
      created_at: iso(40 * 24 * 60 * MINUTE),
      people: 1,
      task_quota_per_year: null,
      runs_per_user: 5,
      domains: [],
    },
    {
      org_id: EMPTY_ORG,
      name: "Westbury Council",
      created_at: iso(3 * 24 * 60 * MINUTE),
      people: 0,
      task_quota_per_year: null,
      runs_per_user: null,
      domains: ["westbury.gov.uk", "westbury.example"],
    },
    {
      org_id: DHSC,
      name: "DHSC",
      created_at: iso(20 * 24 * 60 * MINUTE),
      people: 0,
      task_quota_per_year: null,
      runs_per_user: null,
      domains: [],
    },
  ];
}

export function cohortFixtures(): Cohort[] {
  return [
    {
      cohort_id: PANEL,
      name: "Priority panel",
      description: "Policy leads from HMT, No.10 and Nesta who test new features first.",
      starts_on: null,
      ends_on: null,
      links: ["https://example.org/panel-notes"],
      created_at: iso(30 * 24 * 60 * MINUTE),
      people: 1,
    },
    {
      cohort_id: PILOT,
      name: "DHSC V3 pilot",
      description: null,
      starts_on: "2026-12-01",
      ends_on: "2027-01-31",
      links: [],
      created_at: iso(2 * 24 * 60 * MINUTE),
      people: 0,
    },
    {
      cohort_id: DHSC_PILOT,
      name: "DHSC pilot 2027",
      description: null,
      starts_on: null,
      ends_on: null,
      links: [],
      created_at: iso(10 * 24 * 60 * MINUTE),
      people: 0,
    },
  ];
}

const DAY = 24 * 60 * MINUTE;
const dhsc = { org_id: DHSC, name: "DHSC" };

/** One link in each state; the first is the design's example, "DHSC pilot". */
export function inviteLinkFixtures(): InviteLink[] {
  const link = (
    id: string,
    label: string,
    code: string,
    fields: Pick<InviteLink, "uses" | "max_uses" | "expires_at" | "state"> & Partial<InviteLink>,
  ): InviteLink => ({
    invite_link_id: id,
    label,
    organisation: dhsc,
    cohorts: [],
    allowed_domains: ["dhsc.example"],
    revoked_at: null,
    created_at: iso(20 * DAY),
    url: `https://policy-atlas.example/#invite=${code}`,
    ...fields,
  });
  return [
    link(LINK_ACTIVE, "DHSC pilot", "K7Q2-M9XD-3FHP", {
      cohorts: [{ cohort_id: DHSC_PILOT, name: "DHSC pilot 2027" }],
      allowed_domains: ["dhsc.example", "ukhsa.example"],
      uses: 63,
      max_uses: 120,
      expires_at: iso(-80 * DAY),
      state: "active",
    }),
    link("00000000-0000-4000-8000-0000000000a2", "Treasury workshop", "T4WR-8KQN-2MZE", {
      organisation: policyLab,
      allowed_domains: ["hmt.example"],
      uses: 40,
      max_uses: 40,
      expires_at: iso(-55 * DAY),
      state: "full",
    }),
    link("00000000-0000-4000-8000-0000000000a3", "Autumn test", "A9TS-3XPV-7HRK", {
      organisation: nesta,
      allowed_domains: ["nesta.example"],
      uses: 3,
      max_uses: 10,
      expires_at: iso(16 * DAY),
      state: "expired",
    }),
    link("00000000-0000-4000-8000-0000000000a4", "Old pilot", "P2DX-6NWQ-4FTB", {
      uses: 12,
      max_uses: 50,
      expires_at: iso(-6 * DAY),
      revoked_at: iso(2 * DAY),
      state: "revoked",
    }),
  ];
}

const nesta = { org_id: NESTA, name: "Nesta" };
const policyLab = { org_id: POLICY_LAB, name: "Policy Lab" };

export function peopleFixtures(): Person[] {
  return [
    {
      user_id: OPS_ME,
      display_name: "Priya Shah",
      email: "priya.shah@nesta.org.uk",
      organisation: nesta,
      is_admin: true,
      is_ops: true,
      created_at: iso(150 * 24 * 60 * MINUTE),
      invited_at: iso(150 * 24 * 60 * MINUTE),
      first_signed_in_at: iso(149 * 24 * 60 * MINUTE),
      task_quota_per_year: null,
      runs_per_user: null,
      tasks_this_year: 31,
      // An administrator is exempt from both limits.
      limits: { task_quota_per_year: null, runs_per_user: null, task_quota_from: { kind: "administrator" }, runs_from: { kind: "administrator" } },
      cohorts: [{ cohort_id: PANEL, name: "Priority panel" }],
    },
    {
      user_id: "sub-tom",
      display_name: "Tom Ellis",
      email: "tom.ellis@nesta.org.uk",
      organisation: nesta,
      is_admin: false,
      is_ops: false,
      created_at: iso(30 * 24 * 60 * MINUTE),
      invited_at: iso(25 * MINUTE),
      first_signed_in_at: null,
      task_quota_per_year: null,
      runs_per_user: null,
      tasks_this_year: 12,
      limits: { task_quota_per_year: 100, runs_per_user: 3, task_quota_from: { kind: "organisation", name: "Nesta" }, runs_from: { kind: "default" } },
      cohorts: [],
    },
    {
      user_id: "sub-mara",
      display_name: "Mara Okafor",
      email: "mara.okafor@nesta.org.uk",
      organisation: nesta,
      is_admin: false,
      is_ops: false,
      created_at: iso(10 * 24 * 60 * MINUTE),
      invited_at: iso(2 * 60 * MINUTE + 5 * MINUTE),
      first_signed_in_at: iso(60 * MINUTE),
      task_quota_per_year: 0,
      runs_per_user: 6,
      tasks_this_year: 64,
      limits: { task_quota_per_year: null, runs_per_user: 6, task_quota_from: { kind: "person" }, runs_from: { kind: "person" } },
      cohorts: [],
    },
    {
      user_id: "sub-jon",
      display_name: "Jon Reyes",
      email: "jon.reyes@policylab.example",
      organisation: policyLab,
      is_admin: false,
      is_ops: false,
      created_at: iso(5 * 24 * 60 * MINUTE),
      invited_at: null,
      first_signed_in_at: iso(20 * 24 * 60 * MINUTE),
      task_quota_per_year: null,
      runs_per_user: null,
      tasks_this_year: 3,
      limits: { task_quota_per_year: 50, runs_per_user: 5, task_quota_from: { kind: "default" }, runs_from: { kind: "cohort", name: "Policy Lab" } },
      cohorts: [],
    },
    {
      user_id: "sub-sam",
      display_name: "Sam Holt",
      email: "sam.holt@example.com",
      organisation: null,
      is_admin: false,
      is_ops: false,
      created_at: iso(2 * 24 * 60 * MINUTE),
      invited_at: iso(3 * 24 * 60 * MINUTE),
      first_signed_in_at: null,
      task_quota_per_year: null,
      runs_per_user: null,
      tasks_this_year: 0,
      limits: { task_quota_per_year: 50, runs_per_user: 3, task_quota_from: { kind: "default" }, runs_from: { kind: "default" } },
      cohorts: [],
    },
    {
      user_id: "sub-lena",
      display_name: "Lena Brandt",
      email: null,
      organisation: nesta,
      is_admin: false,
      is_ops: true,
      created_at: iso(60 * 24 * 60 * MINUTE),
      invited_at: null,
      first_signed_in_at: iso(10 * 24 * 60 * MINUTE),
      task_quota_per_year: null,
      runs_per_user: null,
      tasks_this_year: 7,
      limits: { task_quota_per_year: 100, runs_per_user: 3, task_quota_from: { kind: "organisation", name: "Nesta" }, runs_from: { kind: "default" } },
      cohorts: [],
    },
    {
      user_id: "sub-ada",
      display_name: "Ada Quinn",
      email: "ada.quinn@example.org",
      organisation: nesta,
      is_admin: false,
      is_ops: false,
      created_at: iso(90 * 24 * 60 * MINUTE),
      invited_at: null,
      first_signed_in_at: iso(80 * 24 * 60 * MINUTE),
      deactivated_at: iso(3 * 24 * 60 * MINUTE),
      task_quota_per_year: null,
      runs_per_user: null,
      tasks_this_year: 4,
      limits: { task_quota_per_year: 100, runs_per_user: 3, task_quota_from: { kind: "organisation", name: "Nesta" }, runs_from: { kind: "default" } },
      cohorts: [],
    },
  ];
}

export function requestFixtures(): Requests {
  const items: AccessRequest[] = [
    {
      entry_id: "00000000-0000-4000-8000-0000000000e1",
      email: "ana.lopez@westbury.gov.uk",
      name: "Ana Lopez",
      organisation: "Westbury Council",
      role_or_reason: "Housing policy lead",
      created_at: iso(40 * MINUTE),
      status: "waiting",
      account_user_id: null,
      account_created_at: null,
      note: null,
      invite: { label: "DHSC pilot", reason: "wrong_domain" },
    },
    {
      entry_id: "00000000-0000-4000-8000-0000000000e2",
      email: "ben.cole@nesta.org.uk",
      name: "Ben Cole",
      organisation: "Nesta",
      role_or_reason: "Analyst",
      created_at: iso(26 * 60 * MINUTE),
      status: "invited",
      account_user_id: "sub-ben",
      account_created_at: iso(25 * 60 * MINUTE),
      note: null,
    },
    {
      entry_id: "00000000-0000-4000-8000-0000000000e3",
      email: "jon.reyes@policylab.example",
      name: "Jon Reyes",
      organisation: null,
      role_or_reason: "Researcher",
      created_at: iso(3 * 24 * 60 * MINUTE),
      status: "check",
      account_user_id: null,
      account_created_at: null,
      note: "Policy Lab",
    },
  ];
  return {
    items,
    self_signup: { enabled: true, domains: ["nesta.org.uk", "westbury.gov.uk"], sent_this_hour: 2, max_per_hour: 100 },
  };
}
