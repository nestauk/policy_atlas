import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MOCK_OPTION_ID_EXCLUDED, MOCK_OPTION_ID_NO_IN_SCOPE, mockLonglist } from "../../mock/fixtures";
import { LonglistView } from "./LonglistView";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
}));

const excludeMutate = vi.fn();
const includeMutate = vi.fn();
const addMutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useAddOption: vi.fn(),
  useExcludeOption: vi.fn(),
  useIncludeOption: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderLonglist(taskOverrides: Partial<{ active_run: unknown }> = {}) {
  vi.mocked(queries.useTask).mockReturnValue(
    {
      data: { name: "NEET task", capability: "options_scoping", active_run: taskOverrides.active_run ?? null },
    } as unknown as ReturnType<
      typeof queries.useTask
    >,
  );
  vi.mocked(mutations.useExcludeOption).mockReturnValue(
    { mutate: excludeMutate, isPending: false } as unknown as ReturnType<typeof mutations.useExcludeOption>,
  );
  vi.mocked(mutations.useIncludeOption).mockReturnValue(
    { mutate: includeMutate, isPending: false } as unknown as ReturnType<typeof mutations.useIncludeOption>,
  );
  vi.mocked(mutations.useAddOption).mockReturnValue(
    { mutate: addMutate, isPending: false } as unknown as ReturnType<typeof mutations.useAddOption>,
  );
  const longlist = mockLonglist();
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
      <Routes>
        <Route path="/tasks/:taskId/result" element={<LonglistView taskId={TASK_ID} longlist={longlist} />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  excludeMutate.mockClear();
  includeMutate.mockClear();
  addMutate.mockClear();
});

describe("LonglistView", () => {
  it("renders the depth tag, its sentence and the counts header", () => {
    renderLonglist();
    expect(screen.getByText("scoping pass")).toBeInTheDocument();
    expect(
      screen.getByText("Screened on titles and abstracts · nothing read in full · document set not confirmed"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("4 options · 2 themes · 3 included · 1 with no in-scope evidence · 1 excluded · 5 records unclustered"),
    ).toBeInTheDocument();
  });

  it("filters rows with the Show control", async () => {
    const user = userEvent.setup();
    renderLonglist();
    expect(screen.getByText("National sanctions regime")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Excluded" }));
    expect(screen.getByText("National sanctions regime")).toBeInTheDocument();
    expect(screen.queryByText("School-based mentoring")).not.toBeInTheDocument();
  });

  it("filters rows with the Setting facet", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const settingGroup = screen.getByRole("group", { name: "Setting" });
    await user.click(within(settingGroup).getByRole("button", { name: "Community centre" }));
    expect(screen.getByText("School-based mentoring")).toBeInTheDocument();
    expect(screen.queryByText("National sanctions regime")).not.toBeInTheDocument();
  });

  it("filters rows with the Where tried facet", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const whereGroup = screen.getByRole("group", { name: "Where tried" });
    await user.click(within(whereGroup).getByRole("button", { name: "Other" }));
    expect(screen.getByText("School-based mentoring")).toBeInTheDocument();
    expect(screen.queryByText("National sanctions regime")).not.toBeInTheDocument();
  });

  it("shows theme sections open by default and collapsible, plus a No theme section", () => {
    renderLonglist();
    const themeHeading = screen.getByText("Conditionality and support").closest("details");
    expect(themeHeading).toHaveAttribute("open");
    expect(screen.getByText("No theme")).toBeInTheDocument();
  });

  it("an option row shows origin, state, exclusion reason and relation", () => {
    renderLonglist();
    const row = screen.getByText("National sanctions regime").closest("li");
    expect(row).not.toBeNull();
    const scoped = within(row as HTMLElement);
    expect(scoped.getByText("clustered from 6 documents")).toBeInTheDocument();
    expect(
      scoped.getByText('excluded: breaks "Only include options a local authority can fund directly"'),
    ).toBeInTheDocument();
    expect(scoped.getByText("part of Universal youth offer bundle")).toBeInTheDocument();
  });

  it("shows a package's has_part relation and the added-by-you entrant's zero-document note", () => {
    renderLonglist();
    const packageRow = screen.getByText("Universal youth offer bundle").closest("li");
    expect(within(packageRow as HTMLElement).getByText("includes National sanctions regime")).toBeInTheDocument();
    const addedRow = screen.getByText("Youth guarantee").closest("li");
    expect(within(addedRow as HTMLElement).getByText("no documents found yet")).toBeInTheDocument();
    expect(within(addedRow as HTMLElement).getByText("added by you")).toBeInTheDocument();
  });

  it("links Do nothing to the baseline", () => {
    renderLonglist();
    const link = screen.getByRole("link", {
      name: "Do nothing — the baseline describes the situation these options would change.",
    });
    expect(link).toHaveAttribute("href", `/tasks/${TASK_ID}/result?view=baseline`);
  });

  it("Exclude asks for a reason and posts once", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    const input = within(row).getByPlaceholderText("Why exclude this option?");
    await user.type(input, "Duplicates the mentoring pilot");
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    expect(excludeMutate).toHaveBeenCalledTimes(1);
    expect(excludeMutate).toHaveBeenCalledWith(
      { optionId: MOCK_OPTION_ID_NO_IN_SCOPE, reason: "Duplicates the mentoring pilot" },
      expect.anything(),
    );
  });

  it("Include again posts once for an excluded option", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const row = screen.getByText("National sanctions regime").closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Include again" }));
    expect(includeMutate).toHaveBeenCalledTimes(1);
    expect(includeMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_EXCLUDED });
  });

  it("Add an option posts once and is disabled while a walk is active", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const input = screen.getByPlaceholderText("Add an option");
    await user.type(input, "A new option");
    await user.click(screen.getByRole("button", { name: "Add an option" }));
    expect(addMutate).toHaveBeenCalledTimes(1);
    expect(addMutate).toHaveBeenCalledWith({ text: "A new option" }, expect.anything());
  });

  it("disables Add an option while a walk is active", () => {
    renderLonglist({ active_run: { capability_run_id: "run-1", status: "running", started_at: "now" } });
    expect(screen.getByPlaceholderText("Add an option")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Add an option" })).toBeDisabled();
  });

  it("toggles to the reduced grid and back", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: "Grid" }));
    expect(screen.getByRole("columnheader", { name: "Do minimum" })).toBeInTheDocument();
    expect(screen.queryByText("Conditionality and support")).not.toBeInTheDocument();
  });
});
