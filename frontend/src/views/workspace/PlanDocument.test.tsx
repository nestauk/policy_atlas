import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "../../api/gen/types";
import { COPY } from "../../lib/vocabulary";
import { TooltipProvider } from "../../ui/radix/Tooltip";
import { PlanDocument } from "./PlanDocument";
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

const PANEL_LABELS = ["Research question", "Settings", "Search filters", "Screening rules"];

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
    backend_scope: "both",
    steering_mode: "moderate",
    time_band: "2-3 days",
    steps: [{ label: "Search the literature", blurb: "Cast a wide net", stage: "acquire" }],
  };
}

function mockUsePlan(overrides: { data?: PlanOut | null; isPending?: boolean; isError?: boolean }) {
  vi.mocked(queries.usePlan).mockReturnValue(
    {
      data: undefined,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
      ...overrides,
    } as unknown as ReturnType<typeof queries.usePlan>,
  );
}

function planOut(plan: PlanDraft): PlanOut {
  return { plan, status: "approved", version: 1 };
}

function renderPlan(onOverlayChange = vi.fn(), overlay = {}) {
  return render(
    <TooltipProvider delayDuration={0}>
      <PlanDocument
        projectId={PROJECT_ID}
        onClose={vi.fn()}
        overlay={overlay}
        onOverlayChange={onOverlayChange}
      />
    </TooltipProvider>,
  );
}

beforeEach(() => {
  vi.mocked(queries.usePlan).mockReset();
});

describe("PlanDocument", () => {
  it("renders the trimmed plan sections", () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    renderPlan();
    for (const label of PANEL_LABELS) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.queryByText("How findings are grouped")).toBeNull();
    expect(screen.getByText("Plan steps")).toBeInTheDocument();
    expect(screen.getByText("Expected run time: ~10-20 min")).toBeInTheDocument();
    expect(screen.getByText("Searching")).toBeInTheDocument();
    expect(screen.getByText("Querying academic and policy databases.")).toBeInTheDocument();
    expect(screen.getByText("2015–2024")).toBeInTheDocument();
    expect(screen.getByText("Source geography")).toBeInTheDocument();
    expect(screen.getByText("Academic + Policy (OpenAlex, Overton)")).toBeInTheDocument();
    expect(screen.getByText("Thoroughness")).toBeInTheDocument();
    expect(screen.getByText("Standard report")).toBeInTheDocument();
    expect(screen.getByText("Analysis level")).toBeInTheDocument();
    expect(screen.getByText("Full-text synthesis")).toBeInTheDocument();
  });

  it("shows none-selected for unset year and geography filters", () => {
    mockUsePlan({ data: planOut(emptyPlan()) });
    renderPlan();
    expect(screen.getByText("Publication years")).toBeInTheDocument();
    expect(screen.getByText("No preference")).toBeInTheDocument();
    expect(screen.getByText("None selected")).toBeInTheDocument();
    expect(screen.getAllByText(COPY.notDecided).length).toBeGreaterThan(0);
  });

  it("updates expected run time and agreed steps from local settings", () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    renderPlan(vi.fn(), { search_effort: "rapid", analysis_depth: "deep" });
    expect(screen.getByText("Expected run time: ~75-90 min")).toBeInTheDocument();
    expect(screen.getByText("Extracting findings")).toBeInTheDocument();
    expect(screen.getByText("Grouping findings")).toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();
  });

  it("adapts the searching step to the selected sources filter", () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    renderPlan(vi.fn(), { backend_scope: "academic_only" });
    expect(screen.getByText("Querying academic databases.")).toBeInTheDocument();
    expect(screen.queryByText("Querying academic and policy databases.")).toBeNull();
  });

  it("picks a settings option from the app-chrome menu, not a native select", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onOverlayChange = vi.fn();
    const user = userEvent.setup();
    renderPlan(onOverlayChange);

    const edits = screen.getAllByRole("button", { name: "Edit" });
    await user.click(edits[1]);
    expect(screen.queryByRole("combobox")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Search scope" }));
    await user.click(screen.getByRole("option", { name: "Focused" }));
    expect(screen.getByRole("button", { name: "Thoroughness" })).toHaveTextContent("Custom");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(onOverlayChange).toHaveBeenCalledWith(
      expect.objectContaining({ search_effort: "rapid", analysis_depth: "standard" }),
    );
  });

  it("snaps both axes when a research-approach preset is picked", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onOverlayChange = vi.fn();
    const user = userEvent.setup();
    renderPlan(onOverlayChange);

    const edits = screen.getAllByRole("button", { name: "Edit" });
    await user.click(edits[1]);
    await user.click(screen.getByRole("button", { name: "Thoroughness" }));
    await user.click(screen.getByRole("option", { name: "Rapid overview" }));
    expect(screen.getByRole("button", { name: "Search scope" })).toHaveTextContent("Focused");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(onOverlayChange).toHaveBeenCalledWith(
      expect.objectContaining({ search_effort: "rapid", analysis_depth: "landscape" }),
    );
  });

  it("keeps the search-scope caps in an info hover, not as body copy", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const user = userEvent.setup();
    renderPlan();
    expect(screen.queryByText(/up to 50 relevant results per database/)).toBeNull();
    await user.hover(screen.getByRole("button", { name: "About Search scope" }));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Focused: up to 50 relevant results per database");
  });

  it("keeps the analysis-level descriptions in an info hover, not as body copy", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const user = userEvent.setup();
    renderPlan();
    expect(screen.queryByText(/Themes, coverage and gaps across the screened evidence/)).toBeNull();
    await user.hover(screen.getByRole("button", { name: "About Analysis level" }));
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "Overview: Themes, coverage and gaps across the screened evidence",
    );
  });

  it("saves the research question locally without a planner turn", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onOverlayChange = vi.fn();
    const user = userEvent.setup();
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument
          projectId={PROJECT_ID}
          onClose={vi.fn()}
          overlay={{}}
          onOverlayChange={onOverlayChange}
        />
      </TooltipProvider>,
    );
    const [questionEdit] = screen.getAllByRole("button", { name: "Edit" });
    await user.click(questionEdit);
    const field = screen.getByDisplayValue("How effective are school meals at raising uptake?");
    await user.clear(field);
    await user.type(field, "A new question");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onOverlayChange).toHaveBeenCalledWith({ question: "A new question" });
  });

  it("calls onClose when the close button is clicked", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument
          projectId={PROJECT_ID}
          onClose={onClose}
          overlay={{}}
          onOverlayChange={vi.fn()}
        />
      </TooltipProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Close the search plan" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("docks from the centre overlay and offers Start search", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onDock = vi.fn();
    const user = userEvent.setup();
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument
          projectId={PROJECT_ID}
          placement="center"
          onClose={vi.fn()}
          onDock={onDock}
          overlay={{}}
          onOverlayChange={vi.fn()}
        />
      </TooltipProvider>,
    );
    expect(screen.getByRole("button", { name: "Start search" }).className).toContain("bg-green");
    await user.click(screen.getByRole("button", { name: "Move the plan to the side" }));
    expect(onDock).toHaveBeenCalledTimes(1);
  });

  it("hides the dock control when already on the side", () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument
          projectId={PROJECT_ID}
          placement="side"
          onClose={vi.fn()}
          onDock={vi.fn()}
          overlay={{}}
          onOverlayChange={vi.fn()}
        />
      </TooltipProvider>,
    );
    expect(screen.queryByRole("button", { name: "Move the plan to the side" })).toBeNull();
    expect(screen.getByRole("button", { name: "Start search" })).toBeInTheDocument();
  });

  it("keeps the title left-aligned in the same column as the sections", () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument
          projectId={PROJECT_ID}
          placement="center"
          onClose={vi.fn()}
          onDock={vi.fn()}
          overlay={{}}
          onOverlayChange={vi.fn()}
        />
      </TooltipProvider>,
    );
    const title = screen.getByRole("heading", { name: "Search plan" });
    expect(title.className).not.toContain("text-center");
    expect(title.parentElement?.className).not.toContain("text-center");
    const column = title.closest("header")?.parentElement?.parentElement;
    expect(column).toContainElement(screen.getByRole("heading", { name: "Research question" }));
  });

  it("renders dock and close as matching icon buttons", () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument
          projectId={PROJECT_ID}
          placement="center"
          onClose={vi.fn()}
          onDock={vi.fn()}
          overlay={{}}
          onOverlayChange={vi.fn()}
        />
      </TooltipProvider>,
    );
    const dock = screen.getByRole("button", { name: "Move the plan to the side" });
    const close = screen.getByRole("button", { name: "Close the search plan" });
    expect(dock.className).toBe(close.className);
    expect(dock.querySelector("svg")?.getAttribute("class")).toBe(
      close.querySelector("svg")?.getAttribute("class"),
    );
  });

  it("hides Edit and Start search when the plan is a read-only record", () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument
          projectId={PROJECT_ID}
          readOnly
          onClose={vi.fn()}
          overlay={{}}
          onOverlayChange={vi.fn()}
        />
      </TooltipProvider>,
    );
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Start search" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Research question" })).toBeInTheDocument();
  });
});
