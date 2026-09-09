import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "../../api/gen/types";
import { PlanCard } from "./PlanCard";
import * as mutations from "../../api/mutations";
import * as queries from "../../api/queries";

type PlanDraft = components["schemas"]["PlanDraft"];
type PlanOut = components["schemas"]["PlanOut"];

vi.mock("../../api/queries", () => ({
  usePlan: vi.fn(),
}));

vi.mock("../../api/mutations", () => ({
  useStartRun: vi.fn(),
  usePatchPlan: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(mutations.useStartRun).mockReturnValue(
    { mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useStartRun>,
  );
  vi.mocked(mutations.usePatchPlan).mockReturnValue(
    { mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.usePatchPlan>,
  );
});

const TASK_ID = "11111111-1111-1111-1111-111111111111";

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

function mockPlanQuery(data: (Omit<PlanOut, "capability"> & { capability?: string }) | undefined) {
  vi.mocked(queries.usePlan).mockReturnValue(
    {
      data: data === undefined ? undefined : { capability: "evidence_search", ...data },
    } as unknown as ReturnType<typeof queries.usePlan>,
  );
}

function renderCard(overrides: Partial<Parameters<typeof PlanCard>[0]> = {}) {
  return render(<PlanCard taskId={TASK_ID} runActive={false} isOwner {...overrides} />);
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

  it("offers Discard edits and start alongside a failed-apply notice, and it starts without a PATCH", async () => {
    mockPlanQuery({ plan: basePlan(), status: "approved", version: 1 });
    const startRunMutate = vi.fn();
    vi.mocked(mutations.useStartRun).mockReturnValue(
      { mutate: startRunMutate, isPending: false } as unknown as ReturnType<typeof mutations.useStartRun>,
    );
    vi.mocked(mutations.usePatchPlan).mockReturnValue(
      {
        mutate: vi.fn((_body, handlers) =>
          handlers.onError(Object.assign(new Error("Geography must be a known ISO country."), { code: "internal" })),
        ),
        isPending: false,
      } as unknown as ReturnType<typeof mutations.usePatchPlan>,
    );
    const onDiscardOverlay = vi.fn();
    const user = userEvent.setup();
    renderCard({ overlay: { geography: "Nowhereland" }, onDiscardOverlay });

    await user.click(screen.getByRole("button", { name: "Start search" }));
    expect(
      screen.getByText("Those plan edits couldn't be saved: Geography must be a known ISO country."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Discard edits and start" }));
    expect(onDiscardOverlay).toHaveBeenCalledTimes(1);
    expect(startRunMutate).toHaveBeenCalledTimes(1);
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

describe("PlanCard — options scoping (task 044)", () => {
  function scopingPlanOut(overrides: { ready?: boolean; status?: string } = {}): PlanOut {
    return {
      capability: "options_scoping",
      plan: null,
      scoping: { ready: overrides.ready ?? true, steps: [] },
      status: overrides.status ?? "approved",
      version: 1,
    } as unknown as PlanOut;
  }

  it("offers only Review the plan — its own start actions live in the opened document", async () => {
    mockPlanQuery(scopingPlanOut());
    const onReviewPlan = vi.fn();
    const user = userEvent.setup();
    renderCard({ onReviewPlan });
    await user.click(screen.getByRole("button", { name: "Review the plan" }));
    expect(onReviewPlan).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Start search" })).not.toBeInTheDocument();
  });

  it("stays hidden until the scoping draft is ready", () => {
    mockPlanQuery(scopingPlanOut({ ready: false }));
    const { container } = renderCard();
    expect(container).toBeEmptyDOMElement();
  });

  it("stays hidden while the plan is a draft, not yet approved", () => {
    mockPlanQuery(scopingPlanOut({ status: "draft" }));
    const { container } = renderCard();
    expect(container).toBeEmptyDOMElement();
  });
});
