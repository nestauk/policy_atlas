import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "../../api/gen/types";
import { COPY } from "../../lib/vocabulary";
import { PlanDocument } from "./PlanDocument";
import * as queries from "../../api/queries";

type PlanDraft = components["schemas"]["PlanDraft"];
type PlanOut = components["schemas"]["PlanOut"];

vi.mock("../../api/queries", () => ({
  usePlan: vi.fn(),
}));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

/** Every part label, read verbatim from `PlanDocument.tsx`'s `PARTS` array,
 *  in the order the document renders them. */
const PART_LABELS = [
  "The question",
  "Scope",
  "What counts as relevant",
  "Limits on the evidence",
  "How widely to search",
  "How deeply to analyse",
  "What the analysis will do",
  "How findings are grouped",
  "What to extract",
  "How long the report should be",
  "When to check in with you",
  "The agreed steps",
  "Assumptions we are making",
  "Roughly how long it will take",
];

/** A plan with every field null/empty — every part is undecided. */
function emptyPlan(): PlanDraft {
  return {
    analysis_depth: null,
    assumptions: null,
    backend_scope: null,
    component_rationale: null,
    components: null,
    expected_artefact_shape: null,
    extract_profiles: null,
    grouping_facets: null,
    question: null,
    ready: false,
    scope_constraints: null,
    scoping_notes: null,
    screening_criteria: null,
    search_effort: null,
    section_budget: null,
    steering_mode: null,
    steps: [],
    time_band: null,
    title: null,
  };
}

/** A plan with every field populated — every part has a value. */
function fullPlan(): PlanDraft {
  return {
    ...emptyPlan(),
    question: "How effective are school meals at raising uptake?",
    ready: true,
    scoping_notes: ["Primary schools only", "England"],
    screening_criteria: ["Peer-reviewed", "Published after 2015"],
    scope_constraints: {
      author_affiliation_countries: ["GB"],
      country_group: null,
      published_after: "2015-01-01",
      published_before: "2024-01-01",
      publisher_country: "GB",
    },
    search_effort: "standard",
    analysis_depth: "standard",
    components: ["screen_full", "extract"],
    grouping_facets: ["intervention"],
    extract_profiles: ["iof"],
    section_budget: 5,
    steering_mode: "moderate",
    steps: [{ label: "Search the literature", blurb: "Cast a wide net", stage: "acquire" }],
    assumptions: ["Assumes uptake is measured consistently across studies"],
    time_band: "2-3 days",
  };
}

function mockUsePlan(overrides: { data?: PlanOut | null; isPending?: boolean; isError?: boolean }) {
  vi.mocked(queries.usePlan).mockReturnValue(
    {
      data: undefined,
      isPending: false,
      isError: false,
      ...overrides,
    } as unknown as ReturnType<typeof queries.usePlan>,
  );
}

function planOut(plan: PlanDraft): PlanOut {
  return { plan, status: "draft", version: 1 };
}

beforeEach(() => {
  vi.mocked(queries.usePlan).mockReset();
});

describe("PlanDocument", () => {
  it("renders every part", () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    render(<PlanDocument projectId={PROJECT_ID} onClose={vi.fn()} />);
    for (const label of PART_LABELS) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("shows every undecided part rather than hiding it", () => {
    mockUsePlan({ data: planOut(emptyPlan()) });
    render(<PlanDocument projectId={PROJECT_ID} onClose={vi.fn()} />);
    for (const label of PART_LABELS) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getAllByText(COPY.notDecided)).toHaveLength(PART_LABELS.length);
  });

  it("shows a populated part's value instead of the not-decided copy", () => {
    const plan = { ...emptyPlan(), question: "How effective are school meals?" };
    mockUsePlan({ data: planOut(plan) });
    render(<PlanDocument projectId={PROJECT_ID} onClose={vi.fn()} />);
    expect(screen.getByText("How effective are school meals?")).toBeInTheDocument();
    expect(screen.getAllByText(COPY.notDecided)).toHaveLength(PART_LABELS.length - 1);
  });

  it("seeds the composer and closes the panel without touching the plan", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onClose = vi.fn();
    const seedSpy = vi.fn();
    window.addEventListener("policy-atlas:seed-composer", seedSpy);
    try {
      const user = userEvent.setup();
      render(<PlanDocument projectId={PROJECT_ID} onClose={onClose} />);
      const [firstChangeThis] = screen.getAllByRole("button", { name: "Change this" });
      await user.click(firstChangeThis);

      expect(seedSpy).toHaveBeenCalledTimes(1);
      const event = seedSpy.mock.calls[0][0] as CustomEvent<string>;
      expect(typeof event.detail).toBe("string");
      expect(event.detail.length).toBeGreaterThan(0);

      // The component imports no mutation — "Change this" only dispatches the
      // seed event and asks the panel to close. There is no PATCH/fetch path
      // to assert against, so the honest check is: the event fired once and
      // the panel's onClose fired, with nothing else in between.
      expect(onClose).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener("policy-atlas:seed-composer", seedSpy);
    }
  });

  it("calls onClose when the close button is clicked", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<PlanDocument projectId={PROJECT_ID} onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "Close the plan" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows a loading line while the plan is pending", () => {
    mockUsePlan({ isPending: true });
    render(<PlanDocument projectId={PROJECT_ID} onClose={vi.fn()} />);
    expect(screen.getByText("Loading the plan…")).toBeInTheDocument();
  });

  it("shows an alert when the plan fails to load", () => {
    mockUsePlan({ isError: true });
    render(<PlanDocument projectId={PROJECT_ID} onClose={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("The plan couldn't be loaded.");
  });
});
