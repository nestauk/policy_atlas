import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { components } from "../../api/gen/types";
import { PlanCard } from "./PlanCard";
import * as queries from "../../api/queries";

type PlanDraft = components["schemas"]["PlanDraft"];
type PlanOut = components["schemas"]["PlanOut"];

vi.mock("../../api/queries", () => ({
  usePlan: vi.fn(),
}));

vi.mock("../../api/mutations", () => ({
  useStartRun: () => ({ mutate: vi.fn(), isPending: false }),
  usePatchPlan: () => ({ mutate: vi.fn(), isPending: false }),
}));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

function basePlan(overrides: Partial<PlanDraft> = {}): PlanDraft {
  return {
    analysis_depth: null,
    assumptions: null,
    backend_scope: null,
    component_rationale: null,
    components: null,
    expected_artefact_shape: null,
    extract_profiles: null,
    grouping_facets: null,
    question: "How effective are school meals at raising uptake?",
    ready: true,
    scope_constraints: null,
    scoping_notes: null,
    screening_criteria: null,
    search_effort: null,
    section_budget: null,
    steering_mode: null,
    time_band: null,
    title: null,
    ...overrides,
  } as PlanDraft;
}

function mockPlanQuery(data: PlanOut | undefined) {
  vi.mocked(queries.usePlan).mockReturnValue(
    { data } as unknown as ReturnType<typeof queries.usePlan>,
  );
}

function renderCard(overrides: Partial<Parameters<typeof PlanCard>[0]> = {}) {
  return render(<PlanCard projectId={PROJECT_ID} runActive={false} isOwner {...overrides} />);
}

describe("PlanCard — ready actions", () => {
  it("renders null when the plan isn't approved", () => {
    mockPlanQuery({ plan: basePlan(), status: "draft", version: 1 });
    const { container } = renderCard();
    expect(container).toBeEmptyDOMElement();
  });

  it("renders Review the plan and Start search when approved and ready", () => {
    mockPlanQuery({ plan: basePlan(), status: "approved", version: 1 });
    renderCard();
    expect(screen.getByTestId("plan-ready-actions")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review the plan" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start search" }).className).toContain("bg-green");
  });

  it("calls onReviewPlan when Review the plan is clicked", async () => {
    mockPlanQuery({ plan: basePlan(), status: "approved", version: 1 });
    const onReviewPlan = vi.fn();
    const user = userEvent.setup();
    renderCard({ onReviewPlan });
    await user.click(screen.getByRole("button", { name: "Review the plan" }));
    expect(onReviewPlan).toHaveBeenCalledTimes(1);
  });

  it("withdraws once the approval has been consumed by a run", () => {
    mockPlanQuery({ plan: basePlan(), status: "approved", version: 1 });
    const { container } = renderCard({ started: true });
    expect(container).toBeEmptyDOMElement();
  });
});

describe("PlanCard — non-owner read-only (task 033 phase 10c, rubric 37)", () => {
  it("keeps Review the plan but hides Start search for a non-owner", () => {
    mockPlanQuery({ plan: basePlan(), status: "approved", version: 1 });
    renderCard({ isOwner: false });
    expect(screen.getByRole("button", { name: "Review the plan" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start search" })).not.toBeInTheDocument();
  });

  it("Review the plan still opens the plan document for a non-owner", async () => {
    mockPlanQuery({ plan: basePlan(), status: "approved", version: 1 });
    const onReviewPlan = vi.fn();
    const user = userEvent.setup();
    renderCard({ isOwner: false, onReviewPlan });
    await user.click(screen.getByRole("button", { name: "Review the plan" }));
    expect(onReviewPlan).toHaveBeenCalledTimes(1);
  });
});
