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
export const SPRING = "00000000-0000-4000-8000-00000000000f";
export const TOMAS = "sub-tomas";

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
    {
      cohort_id: SPRING,
      name: "Spring pilot",
      description: null,
      starts_on: null,
      ends_on: null,
      links: [],
      created_at: iso(20 * 24 * 60 * MINUTE),
      people: 18,
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
    {
      user_id: TOMAS,
      display_name: "Tomás Ferreira",
      email: "tomas.ferreira@example.org",
      organisation: null,
      is_admin: false,
      is_ops: false,
      created_at: iso(45 * 24 * 60 * MINUTE),
      invited_at: null,
      first_signed_in_at: iso(44 * 24 * 60 * MINUTE),
      task_quota_per_year: null,
      runs_per_user: null,
      tasks_this_year: 2,
      limits: { task_quota_per_year: 50, runs_per_user: 3, task_quota_from: { kind: "default" }, runs_from: { kind: "default" } },
      cohorts: [],
    },
  ];
}

/*
 * The announcements' example (design annex § Fixed example data): the
 * cohort Spring pilot (18 people), the organisation Nesta (64) and the
 * person Tomás Ferreira, one person in both groups: 82 chosen. Two
 * unsubscribed from product updates and one deactivated, so a product
 * update reaches 79 and a service notice 81. The People list does not show
 * these 82; the announcement routes alone read them.
 */

/** One person the announcement routes can choose. */
export interface ExamplePerson {
  user_id: string;
  name: string;
  email: string;
  organisation: string;
  spring: boolean;
  nesta: boolean;
  deactivated: boolean;
  unsubscribed: boolean;
}

const FIRST = ["Alex", "Bea", "Cal", "Dana", "Eli", "Fay", "Gus", "Hana", "Ivo", "Jade"];
const LAST = ["Abbott", "Barker", "Carver", "Dunn", "Ellery", "Frost", "Garner", "Hollis", "Irving"];

/** The person who unsubscribes when the mock's list changes before a send. */
export const LATE_UNSUBSCRIBER = "sub-ex-nesta-50";
/** The person who subscribes again then. */
export const RESUBSCRIBER = "sub-kwame";

export function exampleAudience(): ExamplePerson[] {
  const generated = (index: number) => {
    const first = FIRST[index % FIRST.length];
    const last = LAST[Math.floor(index / FIRST.length) % LAST.length];
    return { name: `${first} ${last}`, email: `${first}.${last}@example.org`.toLowerCase() };
  };
  const person = (user_id: string, name: string, email: string, organisation: string, more: Partial<ExamplePerson>) => ({
    user_id,
    name,
    email,
    organisation,
    spring: false,
    nesta: false,
    deactivated: false,
    unsubscribed: false,
    ...more,
  });
  const people: ExamplePerson[] = [
    person(TOMAS, "Tomás Ferreira", "tomas.ferreira@example.org", "Example Trust", {}),
    person("sub-sofia", "Sofia Lindqvist", "sofia.lindqvist@example.org", "Example Council", { spring: true, unsubscribed: true }),
    person("sub-marta", "Marta Nowak", "marta.nowak@example.org", "Example Council", { spring: true, deactivated: true }),
    person("sub-imogen", "Imogen Hale", "imogen.hale@example.org", "Nesta", { nesta: true }),
    person("sub-dev", "Dev Raman", "dev.raman@example.org", "Nesta", { nesta: true }),
    person(RESUBSCRIBER, "Kwame Osei", "kwame.osei@example.org", "Nesta", { nesta: true, unsubscribed: true }),
    person("sub-ana", "Ana Ruiz", "ana.ruiz@example.org", "Nesta", { nesta: true }),
  ];
  let index = 0;
  // 15 more in Spring pilot only, one in both, and 59 more in Nesta only.
  for (let n = 0; n < 15; n++, index++) {
    const { name, email } = generated(index);
    people.push(person(`sub-ex-spring-${n}`, name, email, "Example Council", { spring: true }));
  }
  const both = generated(index++);
  people.push(person("sub-ex-both", both.name, both.email, "Nesta", { spring: true, nesta: true }));
  for (let n = 0; n < 59; n++, index++) {
    const { name, email } = generated(index);
    people.push(person(`sub-ex-nesta-${n + 1}`, name, email, "Nesta", { nesta: true }));
  }
  return people;
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
    self_signup: { enabled: true, domains: ["nesta.org.uk", "westbury.gov.uk"], sent_this_hour: 2, max_per_hour: 100 },
  };
}
