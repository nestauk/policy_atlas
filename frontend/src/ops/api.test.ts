import { describe, expect, it } from "vitest";

import { inferDefaults, type Person } from "./api";

const DEFAULT = { task_quota_per_year: 50, runs_per_user: 3, task_quota_from: "the default", runs_from: "the default" };

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
    limits: DEFAULT,
    ...overrides,
  };
}

describe("inferDefaults", () => {
  it("never reads a default from an administrator, who is exempt from both limits", () => {
    const admin = person({
      user_id: "a",
      is_admin: true,
      limits: { task_quota_per_year: null, runs_per_user: null, task_quota_from: "administrator", runs_from: "administrator" },
    });
    expect(inferDefaults([admin])).toEqual({ tasks: undefined, runs: undefined });
    expect(inferDefaults([admin, person({ user_id: "b" })])).toEqual({ tasks: 50, runs: 3 });
  });

  it("skips anyone whose limit comes from themselves, a cohort or an organisation, per limit", () => {
    const own = person({ user_id: "c", limits: { ...DEFAULT, runs_per_user: 8, runs_from: "this person" } });
    const viaCohort = person({ user_id: "d", limits: { ...DEFAULT, runs_per_user: 5, runs_from: "DHSC pilot" } });
    expect(inferDefaults([own, viaCohort])).toEqual({ tasks: 50, runs: undefined });
  });
});
