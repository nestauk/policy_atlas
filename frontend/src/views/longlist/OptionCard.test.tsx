import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MOCK_OPTION_ID_EXCLUDED, MOCK_OPTION_ID_NO_IN_SCOPE, mockLonglistOptionCards } from "../../mock/fixtures";
import { TooltipProvider } from "../../ui/radix/Tooltip";
import { OptionCard } from "./OptionCard";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
  useOption: vi.fn(),
}));

const excludeMutate = vi.fn();
const includeMutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useExcludeOption: vi.fn(),
  useIncludeOption: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderCard(optionId: string, overrides: Record<string, unknown> = {}) {
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { name: "NEET task" } } as unknown as ReturnType<typeof queries.useTask>,
  );
  vi.mocked(queries.useOption).mockReturnValue(
    {
      data: { ...mockLonglistOptionCards[optionId], ...overrides },
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useOption>,
  );
  vi.mocked(mutations.useExcludeOption).mockReturnValue(
    { mutate: excludeMutate, isPending: false } as unknown as ReturnType<typeof mutations.useExcludeOption>,
  );
  vi.mocked(mutations.useIncludeOption).mockReturnValue(
    { mutate: includeMutate, isPending: false } as unknown as ReturnType<typeof mutations.useIncludeOption>,
  );
  return render(
    <TooltipProvider>
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/options/${optionId}`]}>
        <Routes>
          <Route path="/tasks/:taskId/options/:optionId" element={<OptionCard />} />
        </Routes>
      </MemoryRouter>
    </TooltipProvider>,
  );
}

beforeEach(() => {
  excludeMutate.mockClear();
  includeMutate.mockClear();
});

describe("OptionCard", () => {
  it("renders the breadcrumb, title, depth tag and What it is", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByRole("link", { name: "Longlist" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/result?view=longlist`,
    );
    expect(screen.getByRole("heading", { name: "National sanctions regime" })).toBeInTheDocument();
    expect(screen.getByText("scoping pass")).toBeInTheDocument();
    expect(screen.getByText("A duty to withdraw benefits on refusal of an offer")).toBeInTheDocument();
    expect(screen.getByText("Primary lever type: Enforce existing powers; it also touches Regulate.")).toBeInTheDocument();
    expect(
      screen.getByText("Ambition: Structural. Changes who is entitled to a national benefit, not just how it is delivered."),
    ).toBeInTheDocument();
  });

  it("renders the evidence-base sentences, where tried, and the documents as source cards", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByRole("heading", { name: "What the evidence base holds so far" })).toBeInTheDocument();
    expect(screen.getByText("6 documents: 4 from United Kingdom, 2 from comparable systems (OECD).")).toBeInTheDocument();
    expect(
      screen.getAllByText("6 documents name this option: 3 evaluated it, 2 described it and 1 mentioned it.").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("2 of the 6 were read from the abstract only.")).toBeInTheDocument();
    expect(screen.getByText("Benefit sanctions for young jobseekers: a systematic review")).toBeInTheDocument();
    expect(screen.getAllByText("Evaluated it").length).toBe(2);
    expect(screen.queryByText("A mention is not support.")).not.toBeInTheDocument();
  });

  it("renders the transferability row and the no-in-scope-evidence row where they apply", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.getByText("Transferable to United Kingdom:")).toBeInTheDocument();
    expect(screen.getByText("checked at assessment.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "No in-scope evidence: none of the 4 documents pass Evidence from the UK and other high-income countries only.",
      ),
    ).toBeInTheDocument();
  });

  // F5: the in-scope record exists for every option once the plan restricts
  // scope; the line is for the options with none in scope only.
  it("hides the no-in-scope-evidence row for an option with in-scope evidence", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, { no_in_scope_evidence: false });
    expect(screen.queryByText(/No in-scope evidence:/)).not.toBeInTheDocument();
  });

  // F3: the evidence-search origin names the report section it came from.
  it("names the report section on a from-your-evidence-search option", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, {
      origin: "from_evidence_search",
      from_section: "What works for young people",
      relations: [],
    });
    expect(
      screen.getAllByText("From your evidence search · What works for young people.").length,
    ).toBeGreaterThan(0);
  });

  // Owner ruling 2026-09-24: a duplicate is merged into the kept option.
  it("names the duplicates merged into the option", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, { also_found_as: ["Guarantee scheme", "Job offer"] });
    expect(screen.getByText("Also found as: Guarantee scheme, Job offer")).toBeInTheDocument();
  });

  it("says nothing about merges when there are none", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.queryByText(/Also found as/)).not.toBeInTheDocument();
  });

  it("shows the documents behind an option, including an inherited one", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByText("National activation policy briefing")).toBeInTheDocument();
    expect(screen.getByText(/inherited from a linked task/)).toBeInTheDocument();
    expect(screen.getByText(/feature not stated/)).toBeInTheDocument();
  });

  it("never renders the words \"how sure\"", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.queryByText(/how sure/i)).not.toBeInTheDocument();
  });

  it("Exclude asks for a reason and posts once", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    await user.click(screen.getByRole("button", { name: "Exclude" }));
    await user.type(screen.getByPlaceholderText("Why exclude this option?"), "Duplicates another option");
    await user.click(screen.getByRole("button", { name: "Exclude" }));
    expect(excludeMutate).toHaveBeenCalledTimes(1);
    expect(excludeMutate).toHaveBeenCalledWith(
      { optionId: MOCK_OPTION_ID_NO_IN_SCOPE, reason: "Duplicates another option" },
      expect.anything(),
    );
  });

  it("shows Include again for an excluded option", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByRole("button", { name: "Include again" }));
    expect(includeMutate).toHaveBeenCalledTimes(1);
    expect(includeMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_EXCLUDED }, expect.anything());
  });
});
