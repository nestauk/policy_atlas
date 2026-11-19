import type { AccessRequest, Cohort, Organisation, Person, Requests } from "../api";

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
    self_signup: { enabled: true, domains: ["nesta.org.uk", "westbury.gov.uk"], sent_this_hour: 2, max_per_hour: 20 },
  };
}
