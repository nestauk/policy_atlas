import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QuotaBanner } from "./QuotaBanner";

const meState = vi.hoisted(() => ({
  quota: null as { used: number; limit: number } | null,
}));

vi.mock("../api/queries", () => ({
  useMe: () => ({
    data: { user_id: "policy-lead", display_name: "Ada Lovelace", is_admin: false, task_quota: meState.quota },
  }),
}));

const SENTENCE = "You have reached your usage quota of 50 tasks. Contact your Policy Atlas administrator to request more.";

describe("QuotaBanner", () => {
  beforeEach(() => {
    meState.quota = null;
  });

  it("shows at the limit, with no dismiss control", () => {
    meState.quota = { used: 50, limit: 50 };
    render(<QuotaBanner />);
    expect(screen.getByRole("status")).toHaveTextContent(SENTENCE);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows above the limit", () => {
    meState.quota = { used: 63, limit: 50 };
    render(<QuotaBanner />);
    expect(screen.getByRole("status")).toHaveTextContent(SENTENCE);
  });

  it("does not show below the limit", () => {
    meState.quota = { used: 49, limit: 50 };
    render(<QuotaBanner />);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("does not show for an exempt caller", () => {
    render(<QuotaBanner />);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
