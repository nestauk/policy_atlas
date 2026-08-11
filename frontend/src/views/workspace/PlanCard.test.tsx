import { render, screen } from "@testing-library/react";
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
  return render(<PlanCard projectId={PROJECT_ID} runActive={false} {...overrides} />);
}

describe("PlanCard — the only start surface", () => {
  it("renders null when the plan isn't approved", () => {
    mockPlanQuery({ plan: basePlan(), status: "draft", version: 1 });
    const { container } = renderCard();
    expect(container).toBeEmptyDOMElement();
  });

  it("renders null when there is no plan at all", () => {
    mockPlanQuery(undefined);
    const { container } = renderCard();
    expect(container).toBeEmptyDOMElement();
  });

  it("renders null when the plan is approved but not yet ready", () => {
    mockPlanQuery({ plan: basePlan({ ready: false }), status: "approved", version: 1 });
    const { container } = renderCard();
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the card with the Start affordance when approved and ready", () => {
    mockPlanQuery({ plan: basePlan(), status: "approved", version: 1 });
    renderCard();
    expect(screen.getByTestId("plan-card")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Start the analysis/ })).toBeInTheDocument();
  });

  it("hides the Start footer once the approval has been consumed by a run", () => {
    mockPlanQuery({ plan: basePlan(), status: "approved", version: 1 });
    renderCard({ started: true });
    expect(screen.getByTestId("plan-card")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Start the analysis/ })).toBeNull();
  });
});
