import { fireEvent, render, screen } from "@testing-library/react";
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
  useTask: vi.fn(),
  useRuns: vi.fn(),
  useArtefact: vi.fn(),
}));

vi.mock("../../api/mutations", () => ({
  useStartRun: () => ({ mutate: vi.fn(), isPending: false }),
  usePatchPlan: () => ({ mutate: vi.fn(), isPending: false }),
  useConfirmBaseline: () => ({ mutate: vi.fn(), isPending: false }),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

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
      publisher_source: null,
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
  return { capability: "evidence_search", plan, status: "approved", version: 1 };
}

function renderPlan(onOverlayChange = vi.fn(), overlay = {}) {
  return render(
    <TooltipProvider delayDuration={0}>
      <PlanDocument
        taskId={TASK_ID}
        onClose={vi.fn()}
        overlay={overlay}
        onOverlayChange={onOverlayChange}
      />
    </TooltipProvider>,
  );
}

// --- Options scoping fixtures (task 044) ----------------------------------

type ScopingPlanDraft = components["schemas"]["ScopingPlanDraft"];
type TaskLinkOut = components["schemas"]["TaskLinkOut"];
type RunOut = components["schemas"]["RunOut"];

function fullScopingPlan(overrides: Partial<ScopingPlanDraft> = {}): ScopingPlanDraft {
  return {
    title: "Cutting NEET numbers",
    question: "How can we reduce the number of young people not in education, employment or training?",
    intended_change: { text: "Fewer young people are NEET six months after leaving school.", origin: "from_your_question" },
    target_unit: { text: "16-24 year-olds at risk of becoming NEET", origin: "assumed" },
    where: { text: "United Kingdom", origin: "assumed" },
    outcomes: [{ text: "NEET rate at 6 months", origin: "from_your_question" }],
    depth: "standard",
    constraints: [
      {
        text: "Only options a council can fund directly",
        kind: "requirement",
        origin: "your_call",
        checked_at: "longlist",
        country_group: null,
        published_after: null,
        published_before: null,
        languages: null,
      },
      {
        text: "Prefer a lower cost per participant",
        kind: "preference",
        origin: "your_call",
        checked_at: "assessment",
        country_group: null,
        published_after: null,
        published_before: null,
        languages: null,
      },
      {
        text: "UK evidence only",
        kind: "evidence_restriction",
        origin: "assumed",
        checked_at: "retrieval",
        country_group: null,
        published_after: null,
        published_before: null,
        languages: ["English"],
      },
    ],
    your_context: [
      { text: "We already run a careers service in every school.", type: "present_fact", turn_index: 1, test_as_condition: false },
      { text: "We plan to expand apprenticeships next year.", type: "commitment", turn_index: 2, test_as_condition: true },
    ],
    entry_branch: "explore",
    linked_task_ids: [],
    steering_mode: "moderate",
    steer_point_defaults: [],
    assumptions: [],
    steps: [
      { stage: "acquire", label: "Searching sources", blurb: "Queries out to academic and policy databases." },
      { stage: "synthesise", label: "Writing the baseline", blurb: "Setting out what happens if nothing changes." },
    ],
    time_band: "10-15 minutes",
    baseline_confirmed: null,
    ready: true,
    ...overrides,
  };
}

function scopingPlanOut(overrides: Partial<ScopingPlanDraft> = {}, version = 1): PlanOut {
  return {
    capability: "options_scoping",
    plan: null,
    scoping: fullScopingPlan(overrides),
    status: "approved",
    version,
  };
}

function mockUseTask(links: TaskLinkOut[] = []) {
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { links } } as unknown as ReturnType<typeof queries.useTask>,
  );
}

function mockUseRuns(runs: RunOut[] = []) {
  vi.mocked(queries.useRuns).mockReturnValue(
    { data: { data: runs } } as unknown as ReturnType<typeof queries.useRuns>,
  );
}

function mockUseArtefact(artefactId: string | null) {
  vi.mocked(queries.useArtefact).mockReturnValue(
    { data: artefactId != null ? { artefact_id: artefactId } : null } as unknown as ReturnType<
      typeof queries.useArtefact
    >,
  );
}

function baselineRun(overrides: Partial<RunOut> = {}): RunOut {
  return {
    capability_run_id: "run-1",
    task_id: TASK_ID,
    plan_id: "plan-1",
    plan_version: 1,
    status: "succeeded",
    started_at: "2026-09-01T00:00:00Z",
    ended_at: "2026-09-01T00:20:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(queries.usePlan).mockReset();
  mockUseTask([]);
  mockUseRuns([]);
  mockUseArtefact(null);
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

    // Only the field that actually changed (rapid vs. the plan's "standard")
    // enters the overlay — analysis_depth and steering_mode are unchanged
    // from the plan's own values, so a dirty-only save omits them.
    expect(onOverlayChange).toHaveBeenCalledWith({ search_effort: "rapid" });
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

  it("saves the research question locally without a task_agent turn", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onOverlayChange = vi.fn();
    const user = userEvent.setup();
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument
          taskId={TASK_ID}
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
          taskId={TASK_ID}
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
          taskId={TASK_ID}
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
          taskId={TASK_ID}
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
          taskId={TASK_ID}
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
          taskId={TASK_ID}
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

  it("edits screening rules as separate inputs with add/remove", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onOverlayChange = vi.fn();
    const user = userEvent.setup();
    renderPlan(onOverlayChange);

    const edits = screen.getAllByRole("button", { name: "Edit" });
    await user.click(edits[3]);

    expect(screen.getByDisplayValue("Peer-reviewed")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Published after 2015")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove rule 2" }));
    expect(screen.queryByDisplayValue("Published after 2015")).toBeNull();

    await user.click(screen.getByRole("button", { name: "+ Add rule" }));
    const newField = screen.getByDisplayValue("");
    await user.type(newField, "New rule");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(onOverlayChange).toHaveBeenCalledWith({
      screening_criteria: ["Peer-reviewed", "New rule"],
    });
  });

  it("soft-rejects an overlong screening rule without writing the overlay", async () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    const onOverlayChange = vi.fn();
    const user = userEvent.setup();
    renderPlan(onOverlayChange);

    const edits = screen.getAllByRole("button", { name: "Edit" });
    await user.click(edits[3]);

    const field = screen.getByDisplayValue("Peer-reviewed");
    fireEvent.change(field, { target: { value: "x".repeat(1001) } });
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(onOverlayChange).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("1000");
  });

  it("hides Edit and Start search when the plan is a read-only record", () => {
    mockUsePlan({ data: planOut(fullPlan()) });
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument
          taskId={TASK_ID}
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

describe("PlanDocument — options scoping (task 044)", () => {
  it("renders every scoping section with its Edit action (C18)", () => {
    mockUsePlan({ data: scopingPlanOut() });
    renderPlan();

    expect(screen.getByRole("heading", { name: "Scoping plan" })).toBeInTheDocument();
    const sectionLabels = [
      "Question and intended change",
      "Settings",
      "Constraints and preferences",
      "Your context",
      "Steps and check-ins",
    ];
    for (const label of sectionLabels) {
      expect(screen.getByRole("heading", { name: label })).toBeInTheDocument();
    }
    // Steps and check-ins has no Edit action, matching the ES's own Plan
    // steps section — every other section has one.
    expect(screen.getAllByRole("button", { name: "Edit" })).toHaveLength(sectionLabels.length - 1);
  });

  it("puts text in the Task Agent composer rather than opening an inline editor", async () => {
    mockUsePlan({ data: scopingPlanOut() });
    const user = userEvent.setup();
    const seeded: string[] = [];
    window.addEventListener("policy-atlas:seed-composer", (event) => {
      seeded.push((event as CustomEvent<string>).detail);
    });
    renderPlan();

    await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    expect(seeded).toEqual(["Change the question or intended change: "]);
    // No inline form appeared — the section still shows its read view.
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("hides Starts from with no links", () => {
    mockUsePlan({ data: scopingPlanOut() });
    mockUseTask([]);
    renderPlan();
    expect(screen.queryByRole("heading", { name: "Starts from" })).toBeNull();
  });

  it("shows a flagged link", () => {
    mockUsePlan({ data: scopingPlanOut() });
    mockUseTask([
      {
        link_id: "link-1",
        source_task_id: "source-1",
        source_task_name: "Childhood obesity in Tower Hamlets",
        source_capability_run_id: "run-1",
        flagged: true,
      },
    ]);
    renderPlan();
    expect(screen.getByRole("heading", { name: "Starts from" })).toBeInTheDocument();
    const linkItem = screen
      .getAllByRole("listitem")
      .find((item) => item.textContent?.includes("Evidence search:") === true);
    expect(linkItem?.textContent).toContain("Evidence search: Childhood obesity in Tower Hamlets · linked");
    expect(linkItem?.textContent).toContain("no longer shares a project");
  });

  it("shows the depth screen label, never the internal key", () => {
    mockUsePlan({ data: scopingPlanOut({ depth: "rapid" }) });
    renderPlan();
    expect(screen.getByText("Rapid scoping")).toBeInTheDocument();
    expect(screen.queryByText("rapid")).toBeNull();
  });

  it("shows the check-ins steering words, never the internal key", () => {
    mockUsePlan({ data: scopingPlanOut({ steering_mode: "unattended" }) });
    renderPlan();
    expect(screen.getByText("Run through without asking")).toBeInTheDocument();
  });

  it("renders origin tags with the ES's provenance words", () => {
    mockUsePlan({
      data: scopingPlanOut({
        target_unit: { text: "16-24 year-olds", origin: "assumed" },
        where: { text: "United Kingdom", origin: "your_call" },
      }),
    });
    renderPlan();
    expect(screen.getByText("(assumed, please check)")).toBeInTheDocument();
    expect(screen.getByText("(your choice)")).toBeInTheDocument();
  });

  it("renders the constraints table with the fixed effect sentence per kind and the right Checked at", () => {
    mockUsePlan({ data: scopingPlanOut() });
    renderPlan();

    expect(screen.getByText("Only options a council can fund directly")).toBeInTheDocument();
    expect(
      screen.getByText("Options that conflict are excluded, with the reason shown. You can include them again."),
    ).toBeInTheDocument();
    expect(screen.getByText("Longlist")).toBeInTheDocument();

    expect(
      screen.getByText(
        "Checked after assessment where costs or effects are comparable. Until then, a labelled guess that sorts and never excludes.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Assessment")).toBeInTheDocument();

    expect(screen.getByText("Retrieval")).toBeInTheDocument();
    expect(screen.getByText("Language: not yet applied at retrieval")).toBeInTheDocument();
  });

  it("renders Your context entries with their type word and test-as-condition flag", () => {
    mockUsePlan({ data: scopingPlanOut() });
    renderPlan();
    expect(screen.getByText(/We already run a careers service/)).toBeInTheDocument();
    expect(screen.getByText("(present fact)")).toBeInTheDocument();
    expect(screen.getByText("(commitment, test as a condition)")).toBeInTheDocument();
  });

  it("hides Your context entirely when there are none", () => {
    mockUsePlan({ data: scopingPlanOut({ your_context: [] }) });
    renderPlan();
    expect(screen.queryByRole("heading", { name: "Your context" })).toBeNull();
  });

  describe("start actions (owner correction 2026-09-09)", () => {
    it("no baseline walk yet: one primary action with the time band under it", () => {
      mockUsePlan({ data: scopingPlanOut() });
      mockUseRuns([]);
      renderPlan();
      expect(screen.getByRole("button", { name: "Confirm and build baseline" })).toBeInTheDocument();
      expect(screen.getByText("10-15 minutes")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Rebuild baseline" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Confirm plan and build longlist" })).toBeNull();
    });

    it("the latest walk is running or paused: no start actions — the gate's card and chat decide", () => {
      mockUsePlan({ data: scopingPlanOut(undefined, 1) });
      mockUseRuns([baselineRun({ status: "paused", plan_version: 1 })]);
      renderPlan();
      expect(screen.queryByRole("button", { name: "Confirm and build baseline" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Rebuild baseline" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Confirm plan and build longlist" })).toBeNull();
      expect(screen.queryByText("Plan confirmed", { exact: false })).toBeNull();
    });

    it("the latest walk finished and the plan has since moved to a later version: two actions", () => {
      mockUsePlan({ data: scopingPlanOut(undefined, 2) });
      mockUseRuns([baselineRun({ plan_version: 1 })]);
      mockUseArtefact("artefact-1");
      renderPlan();
      expect(screen.getByRole("button", { name: "Rebuild baseline" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Confirm plan and build longlist" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Confirm and build baseline" })).toBeNull();
    });

    it("an aborted walk (Change the plan) at the same version: also two actions", () => {
      mockUsePlan({ data: scopingPlanOut(undefined, 1) });
      mockUseRuns([baselineRun({ status: "aborted", plan_version: 1 })]);
      mockUseArtefact("artefact-1");
      renderPlan();
      expect(screen.getByRole("button", { name: "Rebuild baseline" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Confirm plan and build longlist" })).toBeInTheDocument();
    });

    it("once baseline_confirmed names the current version: no button", () => {
      mockUsePlan({
        data: scopingPlanOut({ baseline_confirmed: { artefact_id: "artefact-1", plan_version: 1 } }, 1),
      });
      mockUseRuns([baselineRun({ plan_version: 1 })]);
      mockUseArtefact("artefact-1");
      renderPlan();
      expect(
        screen.getByText("Plan confirmed · the longlist arrives with the next stage"),
      ).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Rebuild baseline" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Confirm and build baseline" })).toBeNull();
    });

    it("the latest walk succeeded and the plan hasn't moved since: confirmed, even with no baseline_confirmed record yet", () => {
      mockUsePlan({ data: scopingPlanOut({ baseline_confirmed: null }, 1) });
      mockUseRuns([baselineRun({ plan_version: 1 })]);
      mockUseArtefact("artefact-1");
      renderPlan();
      expect(
        screen.getByText("Plan confirmed · the longlist arrives with the next stage"),
      ).toBeInTheDocument();
    });
  });

  it("hides Edit and the start area when the plan is a read-only record", () => {
    mockUsePlan({ data: scopingPlanOut() });
    render(
      <TooltipProvider delayDuration={0}>
        <PlanDocument taskId={TASK_ID} readOnly onClose={vi.fn()} overlay={{}} onOverlayChange={vi.fn()} />
      </TooltipProvider>,
    );
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Confirm and build baseline" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Question and intended change" })).toBeInTheDocument();
  });
});
