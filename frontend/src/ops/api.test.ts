import { describe, expect, it } from "vitest";

import { inferDefaults, type Organisation, type Person } from "./api";

const org: Organisation = {
  org_id: "o1",
  name: "Nesta",
  created_at: "2026-01-01T00:00:00Z",
  people: 2,
  task_quota_per_year: null,
  runs_per_user: null,
  domains: [],
};

function person(overrides: Partial<Person>): Person {
  return {
    user_id: "u",
    display_name: "P",
    email: null,
    organisation: { org_id: "o1", name: "Nesta" },
    is_admin: false,
    is_ops: false,
    cohorts: [],
    created_at: "2026-01-01T00:00:00Z",
    invited_at: null,
    task_quota_per_year: null,
    runs_per_user: null,
    tasks_this_year: 0,
    limits: { task_quota_per_year: 50, runs_per_user: 3 },
    ...overrides,
  };
}

describe("inferDefaults", () => {
  it("never reads a default from an administrator, who is exempt from both limits", () => {
    const admin = person({ user_id: "a", is_admin: true, limits: { task_quota_per_year: null, runs_per_user: null } });
    expect(inferDefaults([admin], [org])).toEqual({ tasks: undefined, runs: undefined });
    expect(inferDefaults([admin, person({ user_id: "b" })], [org])).toEqual({ tasks: 50, runs: 3 });
  });

  it("skips anyone whose own or organisation's override sets the limit", () => {
    const own = person({ user_id: "c", runs_per_user: 8, limits: { task_quota_per_year: 50, runs_per_user: 8 } });
    const viaOrg = person({ user_id: "d", organisation: { org_id: "o2", name: "Lab" }, limits: { task_quota_per_year: 50, runs_per_user: 5 } });
    const lab: Organisation = { ...org, org_id: "o2", name: "Lab", runs_per_user: 5 };
    expect(inferDefaults([own, viaOrg], [org, lab]).runs).toBeUndefined();
  });
});
