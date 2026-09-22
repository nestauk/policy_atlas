import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MOCK_OPTION_ID_EXCLUDED, MOCK_OPTION_ID_NO_IN_SCOPE, mockLonglistOptionCards } from "../../mock/fixtures";
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

function renderCard(optionId: string) {
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { name: "NEET task" } } as unknown as ReturnType<typeof queries.useTask>,
  );
  vi.mocked(queries.useOption).mockReturnValue(
    {
      data: mockLonglistOptionCards[optionId],
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
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/options/${optionId}`]}>
      <Routes>
        <Route path="/tasks/:taskId/options/:optionId" element={<OptionCard />} />
      </Routes>
    </MemoryRouter>,
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
    expect(screen.getByText("a duty to withdraw benefits on refusal of an offer")).toBeInTheDocument();
    expect(screen.getByText("Lever: Enforce existing powers · also touches: Regulate")).toBeInTheDocument();
    expect(
      screen.getByText("Ambition: Structural — Changes who is entitled to a national benefit, not just how it is delivered."),
    ).toBeInTheDocument();
    expect(screen.getByText("as described, not measured · Policy Atlas's reasoning")).toBeInTheDocument();
  });

  it("renders Where tried, the evidence-base sentences and the closing line", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByRole("heading", { name: "Where tried" })).toBeInTheDocument();
    expect(screen.getByText("United Kingdom 4 · comparable systems (OECD) 2 · other 0 · unknown 0")).toBeInTheDocument();
    expect(
      screen.getByText("6 documents name this option; 3 evaluated it, 2 described it, 0 recommended it, 1 mentioned it."),
    ).toBeInTheDocument();
    expect(screen.getByText("A mention is not support.")).toBeInTheDocument();
  });

  it("renders the transferability row and the no-in-scope-evidence row where they apply", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.getByText("Transferable to your Where: checked at assessment")).toBeInTheDocument();
    expect(
      screen.getByText(
        "No in-scope evidence: none of the 4 documents pass Evidence from the UK and other high-income countries only.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the documents behind an option, including an inherited one", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByText("Show the documents"));
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
    expect(includeMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_EXCLUDED });
  });
});
