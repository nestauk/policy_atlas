import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MOCK_OPTION_ID_NO_IN_SCOPE, mockLonglist } from "../../mock/fixtures";
import { ShortlistView } from "./ShortlistView";
import { CARD_FROM_SHORTLIST } from "./OptionCard";
import { PublicViewProvider } from "../publicView";
import { RISK_APPETITE_LABELS } from "../workspace/planVocabulary";
import {
  MOCK_OPTION_ID_ADDED_BY_YOU,
  MOCK_OPTION_ID_PACKAGE,
} from "../../mock/fixtures";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";
import * as shortlistNote from "./shortlistNote";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
  usePlan: vi.fn(),
  useRuns: vi.fn(),
}));

const excludeMutate = vi.fn();
const includeMutate = vi.fn();
const addMutate = vi.fn();

const shortlistMutate = vi.fn();
const unshortlistMutate = vi.fn();
const suggestMutate = vi.fn();
const patchMutate = vi.fn();
/** The error Suggest more's mutation reports; null while it has not failed. */
let suggestError: unknown = null;

vi.mock("../../api/mutations", () => ({
  useAddOption: vi.fn(),
  useOptionVerb: vi.fn(),
  useShortlistVerb: vi.fn(),
  useSuggestMore: vi.fn(),
  usePatchPlan: vi.fn(),
}));

const noteMutate = vi.fn();
let notePending = false;
vi.mock("./shortlistNote", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./shortlistNote")>()),
  useRefreshShortlistNote: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderShortlist(
  taskOverrides: Partial<{ active_run: unknown }> = {},
  adjust?: (longlist: ReturnType<typeof mockLonglist>) => void,
  runs: { purpose?: string | null; status: string; capability_run_id: string }[] = [],
  where: string | null = null,
) {
  vi.mocked(queries.useTask).mockReturnValue(
    {
      data: { name: "NEET task", capability: "options_scoping", active_run: taskOverrides.active_run ?? null },
    } as unknown as ReturnType<
      typeof queries.useTask
    >,
  );
  vi.mocked(queries.usePlan).mockReturnValue(
    {
      data: { scoping: { question: "How can we cut the NEET rate?", where: where === null ? null : { text: where } } },
    } as unknown as ReturnType<typeof queries.usePlan>,
  );
  vi.mocked(mutations.useOptionVerb).mockImplementation(
    (_taskId, verb) =>
      ({ mutate: verb === "exclude" ? excludeMutate : includeMutate, isPending: false }) as unknown as ReturnType<
        typeof mutations.useOptionVerb
      >,
  );
  vi.mocked(mutations.useShortlistVerb).mockImplementation(
    (_taskId, verb) =>
      ({ mutate: verb === "shortlist" ? shortlistMutate : unshortlistMutate, isPending: false }) as unknown as ReturnType<
        typeof mutations.useShortlistVerb
      >,
  );
  vi.mocked(mutations.useSuggestMore).mockReturnValue(
    { mutate: suggestMutate, isPending: false, isError: suggestError !== null, error: suggestError } as unknown as ReturnType<
      typeof mutations.useSuggestMore
    >,
  );
  vi.mocked(mutations.usePatchPlan).mockReturnValue(
    { mutate: patchMutate, isPending: false, isError: false } as unknown as ReturnType<typeof mutations.usePatchPlan>,
  );
  vi.mocked(queries.useRuns).mockReturnValue({ data: { data: runs } } as unknown as ReturnType<typeof queries.useRuns>);
  vi.mocked(mutations.useAddOption).mockReturnValue(
    { mutate: addMutate, isPending: false } as unknown as ReturnType<typeof mutations.useAddOption>,
  );
  vi.mocked(shortlistNote.useRefreshShortlistNote).mockImplementation(
    () => ({ mutate: noteMutate, isPending: notePending }) as unknown as ReturnType<typeof shortlistNote.useRefreshShortlistNote>,
  );
  const longlist = mockLonglist();
  adjust?.(longlist);
  return render(
    <PublicViewProvider value={publicLink}>
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
        <Routes>
          <Route path="/tasks/:taskId/result" element={<ShortlistView taskId={TASK_ID} longlist={longlist} />} />
        </Routes>
      </MemoryRouter>
    </PublicViewProvider>,
  );
}

/** Whether the next render sits in the public link's view (round 12). */
let publicLink = false;

beforeEach(() => {
  publicLink = false;
  shortlistMutate.mockClear();
  unshortlistMutate.mockClear();
  suggestMutate.mockClear();
  patchMutate.mockClear();
  suggestError = null;
  excludeMutate.mockClear();
  includeMutate.mockClear();
  addMutate.mockClear();
  noteMutate.mockClear();
  notePending = false;
});

describe("ShortlistView — the Shortlist result view (task 055)", () => {
  async function openShortlist(
    taskOverrides: Parameters<typeof renderShortlist>[0] = {},
    adjust?: Parameters<typeof renderShortlist>[1],
    runs?: Parameters<typeof renderShortlist>[2],
  ) {
    const user = userEvent.setup();
    renderShortlist(taskOverrides, adjust, runs);
    return user;
  }

  const open = (longlist: ReturnType<typeof mockLonglist>, id: string, state: "proposed" | "added_by_you" | "set_aside" | null) => {
    const option = longlist.options?.find((entry) => entry.option_id === id);
    if (option === undefined) throw new Error("fixture option missing");
    option.shortlist = state === null ? null : { state, reason: state === "proposed" ? "Because." : null };
  };

  it("renders the title, the appetite select, both groups and the rows", async () => {
    await openShortlist();
    // The longlist's header (round 10): "Shortlist", the question under it.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/^Shortlist$/);
    expect(screen.getByText("How can we cut the NEET rate?")).toHaveClass("text-grey");
    expect(screen.getByRole("combobox", { name: "Risk appetite" })).toHaveTextContent(RISK_APPETITE_LABELS.mostly_tried);
    // No baseline line and no facts strip (owner, 2026-10-27).
    expect(screen.queryByText(/situation today/)).not.toBeInTheDocument();
    const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
    expect(headings.slice(0, 2)).toEqual(["Added by you", "Policy Atlas's picks"]);
    // The pick: name, the option's description, the lever and the footing in
    // plain words, then Policy Atlas's reason under its label, and Remove.
    expect(screen.getByRole("link", { name: "Universal youth offer bundle" })).toBeInTheDocument();
    // Round 10 (C4): a bold "Why:" lead-in on the line, no uppercase label over it.
    const reason = screen.getByText(/Mock reason: names a fact on the card\./);
    expect(reason).toHaveTextContent(/^Why: Mock reason: names a fact on the card\.$/);
    expect(within(reason).getByText("Why:").tagName).toBe("STRONG");
    expect(screen.queryByText("Policy Atlas's reason")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Shortlist$/i, { selector: "p" })).not.toBeInTheDocument();
    expect(screen.getAllByText(/Evaluated, including a review/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/4 observational/)).not.toBeInTheDocument();
    expect(screen.getByText(/Proposed, not yet implemented/)).toBeInTheDocument();
    // Round 10 (finding 6): each place's toggle says Shortlisted, pressed.
    const toggles = screen.getAllByRole("button", { name: "Remove from shortlist" });
    expect(toggles).toHaveLength(2);
    for (const toggle of toggles) expect(toggle).toHaveAttribute("aria-pressed", "true");
  });

  it("puts a user place's row reason as 'Added by you' and lists places alphabetically within a group", async () => {
    await openShortlist({}, (longlist) => {
      open(longlist, MOCK_OPTION_ID_NO_IN_SCOPE, "added_by_you");
    });
    const addedGroup = screen.getByRole("heading", { name: "Added by you" }).closest("section") as HTMLElement;
    const names = within(addedGroup).getAllByRole("link").map((link) => link.textContent);
    expect(names).toEqual(["School-based mentoring", "Youth guarantee"]);
    expect(within(addedGroup).getAllByText("Added by you").length).toBeGreaterThan(0);
  });

  it("calls Remove from shortlist for a place", async () => {
    const user = await openShortlist();
    const row = screen.getByRole("link", { name: "Universal youth offer bundle" }).closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Remove from shortlist" }));
    expect(unshortlistMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_PACKAGE }, expect.anything());
  });

  // Round 12 (owner): the public link reads the shortlist and changes nothing.
  it("is read-only on the public link: the appetite as words, no toggle, Suggest more, Add more or Assess", async () => {
    publicLink = true;
    await openShortlist();
    expect(screen.queryByRole("combobox", { name: "Risk appetite" })).not.toBeInTheDocument();
    expect(screen.getByText(RISK_APPETITE_LABELS.mostly_tried)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^(Add to|Remove from) shortlist$/ })).not.toBeInTheDocument();
    expect(screen.getAllByText("Shortlisted").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Suggest more" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Add more from the longlist" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Assess/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Suggest more asks/)).not.toBeInTheDocument();
  });

  it("patches the plan with the appetite only when the select changes", async () => {
    const user = await openShortlist();
    await user.click(screen.getByRole("combobox", { name: "Risk appetite" }));
    await user.click(screen.getByRole("option", { name: RISK_APPETITE_LABELS.tried_only }));
    expect(patchMutate).toHaveBeenCalledWith({ scoping: { risk_appetite: "tried_only" } });
  });

  it("disables the appetite control while a walk runs and says Shortlisting", async () => {
    await openShortlist({ active_run: { capability_run_id: "x", status: "running", started_at: "2026-10-27T00:00:00Z" } });
    expect(screen.getByRole("combobox", { name: "Risk appetite" })).toBeDisabled();
    expect(screen.getByText("Shortlisting…")).toBeInTheDocument();
  });

  it("Suggest more is disabled with its reason when nothing is left to propose and the shortlist is current", async () => {
    await openShortlist({}, (longlist) => {
      longlist.shortlist.stale = false;
    });
    // Round 10 (finding 4): the reason is words under it, not a tooltip.
    const button = screen.getByRole("button", { name: "Suggest more" });
    expect(button).toBeDisabled();
    expect(button).not.toHaveAttribute("title");
    expect(screen.getByText("Nothing left to propose.")).toBeVisible();
    expect(button).toHaveAccessibleDescription("Nothing left to propose.");
  });

  it("Suggest more is disabled while a walk runs", async () => {
    await openShortlist(
      { active_run: { capability_run_id: "x", status: "running", started_at: "2026-10-27T00:00:00Z" } },
      (longlist) => open(longlist, MOCK_OPTION_ID_NO_IN_SCOPE, null),
    );
    const button = screen.getByRole("button", { name: "Suggest more" });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription("A walk is running.");
  });

  it("Suggest more posts once when an included option is left", async () => {
    const user = await openShortlist({}, (longlist) => open(longlist, MOCK_OPTION_ID_NO_IN_SCOPE, null));
    await user.click(screen.getByRole("button", { name: "Suggest more" }));
    expect(suggestMutate).toHaveBeenCalledTimes(1);
  });

  it("shows the stale line and enables Suggest more to re-propose when the proposal is stale", async () => {
    // Nothing is open, but a stale shortlist re-proposes.
    const user = await openShortlist({}, (longlist) => {
      longlist.shortlist.stale = true;
    });
    expect(screen.getByText("The plan has changed. Suggest more to update the picks.")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Suggest more" });
    expect(button).toBeEnabled();
    expect(button).not.toHaveAttribute("aria-describedby");
    await user.click(button);
    expect(suggestMutate).toHaveBeenCalledTimes(1);
  });

  it("names the plan's Where in the setting words while the longlist matches the plan", async () => {
    renderShortlist({}, (longlist) => open(longlist, MOCK_OPTION_ID_NO_IN_SCOPE, "added_by_you"), [], "England");
    expect(screen.getByText(/Evaluated, not in England, last before/)).toBeInTheDocument();
  });

  it("falls back to 'not in your setting' after a plan change, before the Rebuild", async () => {
    renderShortlist(
      {},
      (longlist) => {
        open(longlist, MOCK_OPTION_ID_NO_IN_SCOPE, "added_by_you");
        longlist.plan_inputs_changed = true;
      },
      [],
      "France",
    );
    expect(screen.getByText(/Evaluated, not in your setting, last before/)).toBeInTheDocument();
    expect(screen.queryByText(/not in France/)).not.toBeInTheDocument();
  });

  it("words a plan_stale refusal of Suggest more as a Rebuild, not a Task Agent message", async () => {
    suggestError = { code: "plan_stale" };
    await openShortlist();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The plan has changed since the longlist was built. Rebuild the longlist first.",
    );
  });

  it("omits the stale line when the proposal is current", async () => {
    await openShortlist({}, (longlist) => {
      longlist.shortlist.stale = false;
    });
    expect(screen.queryByText("The plan has changed. Suggest more to update the picks.")).not.toBeInTheDocument();
  });

  it("shows the not-covered note after its bold lead-in (round 10, C4)", async () => {
    await openShortlist({}, (longlist) => {
      longlist.shortlist.note = "Nothing here tackles the wider labour market.";
    });
    expect(screen.getByText(/Nothing here tackles the wider labour market\./)).toHaveTextContent(
      /^Not covered: Nothing here tackles the wider labour market\.$/,
    );
    expect(screen.queryByText("What this shortlist leaves out")).not.toBeInTheDocument();
  });

  it("hides the note when the note is null", async () => {
    await openShortlist({}, (longlist) => {
      longlist.shortlist.note = null;
    });
    expect(screen.queryByText("Not covered:")).not.toBeInTheDocument();
  });

  it("adds the provenance footer only when it carries a total", async () => {
    await openShortlist({}, (longlist) => {
      longlist.shortlist.note = "A note.";
      longlist.shortlist.provenance = { document_lines_cut: 12, document_lines_total: 100, baseline_chars_cut: 40 };
    });
    expect(screen.getByText("Policy Atlas read 88 of 100 document lines")).toBeInTheDocument();
    expect(screen.getByText("The baseline was cut")).toBeInTheDocument();
  });

  it("leaves the document-lines footer out when the provenance has no total", async () => {
    await openShortlist({}, (longlist) => {
      longlist.shortlist.note = "A note.";
      longlist.shortlist.provenance = { document_lines_cut: 12 };
    });
    expect(screen.queryByText(/document lines/)).not.toBeInTheDocument();
  });

  // Round 10 (finding 4): one primary, Assess; while it is off its reason
  // is the line under it. Suggest more is a secondary.
  it("makes Assess the page's one primary, off with its reason in words", async () => {
    const { container } = renderShortlist();
    const assess = screen.getByRole("button", { name: "Assess these 2" });
    expect(assess).toBeDisabled();
    expect(assess).toHaveAccessibleDescription("Assessment is not yet available.");
    expect(container.querySelectorAll(".cutout, .cutout-sm")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Suggest more" }).className).not.toMatch(/cutout|bg-blue/);
  });

  it("links back to the longlist instead of repeating it", async () => {
    await openShortlist();
    expect(screen.queryByRole("heading", { name: "Other options" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add more from the longlist" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/result`,
    );
    expect(screen.getByRole("button", { name: "Suggest more" })).toBeInTheDocument();
  });

  it("says Policy Atlas is proposing while a walk runs and nothing is placed yet", async () => {
    await openShortlist(
      { active_run: { capability_run_id: "x", status: "running", started_at: "2026-10-27T00:00:00Z" } },
      (longlist) => {
        for (const option of longlist.options ?? []) option.shortlist = null;
      },
    );
    expect(screen.getByText("Policy Atlas is proposing a shortlist…")).toBeInTheDocument();
  });

  it("shows the could-not-propose notice only when the newest walk is a failed shortlist walk", async () => {
    await openShortlist({}, undefined, [{ capability_run_id: "r1", purpose: "shortlist", status: "degraded" }]);
    expect(screen.getByText("Policy Atlas could not propose. Your places are unchanged.")).toBeInTheDocument();
  });

  it("shows no notice for an unrelated degraded walk or a succeeded shortlist walk", async () => {
    await openShortlist({}, undefined, [{ capability_run_id: "r1", purpose: "longlist", status: "degraded" }]);
    expect(screen.queryByText(/could not propose/)).not.toBeInTheDocument();
  });

  it("shows a breach notice on a user place that a constraint now excludes", async () => {
    await openShortlist({}, (longlist) => {
      const option = longlist.options?.find((entry) => entry.option_id === MOCK_OPTION_ID_ADDED_BY_YOU);
      if (option === undefined) throw new Error("fixture option missing");
      option.state = "excluded";
      option.exclusion = { by: "constrain", constraint: "Only include options a local authority can fund directly", reason: "It needs national funding." };
    });
    const notice = screen.getByText(/It needs national funding\./);
    expect(within(notice).getByText("Excluded:")).toHaveClass("text-red");
  });

});

// Owner, 2026-11-08: the "Not covered" note kept current without a call per
// change: once on opening when stale; after changes, one call 3 s after the
// last; none when fresh; never on the public link.
describe("ShortlistView, the note kept current", () => {
  type Longlist = ReturnType<typeof mockLonglist>;
  const staleNote = (stale: boolean) => (longlist: Longlist) => {
    longlist.shortlist = { ...longlist.shortlist, note: "Nothing on housing.", note_stale: stale } as Longlist["shortlist"];
  };
  const tree = (longlist: Longlist) => (
    <PublicViewProvider value={false}>
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
        <Routes>
          <Route path="/tasks/:taskId/result" element={<ShortlistView taskId={TASK_ID} longlist={longlist} />} />
        </Routes>
      </MemoryRouter>
    </PublicViewProvider>
  );

  it("rewrites a stale note once on opening, and says it is behind until then", () => {
    renderShortlist({}, staleNote(true));
    expect(noteMutate).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Written before your latest changes.")).toHaveClass("text-meta", "text-grey");
  });

  it("asks nothing when the note is fresh, then or later", () => {
    vi.useFakeTimers();
    try {
      renderShortlist({}, staleNote(false));
      vi.advanceTimersByTime(10_000);
      expect(noteMutate).not.toHaveBeenCalled();
      expect(screen.queryByText("Written before your latest changes.")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("waits 3 s after the last change, one timer reset by each change, then rewrites once", () => {
    vi.useFakeTimers();
    try {
      const { rerender, unmount } = renderShortlist({}, staleNote(false));
      const changed = (held: string[]) => {
        const next = mockLonglist();
        staleNote(true)(next);
        for (const option of next.options ?? []) {
          if (held.includes(option.option_id)) option.shortlist = { state: "added_by_you", reason: null };
        }
        return next;
      };
      rerender(tree(changed([MOCK_OPTION_ID_NO_IN_SCOPE])));
      vi.advanceTimersByTime(2000);
      rerender(tree(changed([MOCK_OPTION_ID_NO_IN_SCOPE, MOCK_OPTION_ID_PACKAGE])));
      vi.advanceTimersByTime(2900);
      expect(noteMutate).not.toHaveBeenCalled();
      vi.advanceTimersByTime(100);
      expect(noteMutate).toHaveBeenCalledTimes(1);
      // A later change, then leaving the page: the timer is cancelled.
      rerender(tree(changed([MOCK_OPTION_ID_PACKAGE])));
      unmount();
      vi.advanceTimersByTime(5000);
      expect(noteMutate).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  // Owner, 2026-11-08: no breathing words; the Task Agent's working line in
  // the note's place, then the new note fades in.
  it("shows the turning mark and Reviewing the shortlist for gaps in the note's place while it is rewritten", () => {
    notePending = true;
    const { rerender } = renderShortlist({}, staleNote(true));
    const line = screen.getByRole("status");
    expect(line).toHaveTextContent(/^Reviewing the shortlist for gaps$/);
    expect(line.querySelector("svg")).not.toBeNull();
    expect(screen.queryByText(/Nothing on housing\./)).not.toBeInTheDocument();
    expect(document.querySelector(".anim-breathe-soft")).toBeNull();
    expect(screen.queryByText("Written before your latest changes.")).not.toBeInTheDocument();
    // The new note lands: it replaces the line with the arrivals' fade.
    notePending = false;
    const next = mockLonglist();
    next.shortlist = { ...next.shortlist, note: "Nothing on transport.", note_stale: false } as Longlist["shortlist"];
    rerender(tree(next));
    expect(screen.queryByText("Reviewing the shortlist for gaps")).not.toBeInTheDocument();
    expect(screen.getByText(/Nothing on transport\./).closest("p")).toHaveClass("anim-swap-in");
  });

  it("does not fade the note the page opened with", () => {
    renderShortlist({}, staleNote(false));
    expect(screen.getByText(/Nothing on housing\./).closest("p")).not.toHaveClass("anim-swap-in");
  });

  it("asks nothing on the public link", () => {
    publicLink = true;
    renderShortlist({}, staleNote(true));
    expect(noteMutate).not.toHaveBeenCalled();
    expect(screen.queryByText("Written before your latest changes.")).not.toBeInTheDocument();
  });
});

// Round 15 (owner): the Shortlist page's option links tell the card where
// it was opened from, so its breadcrumb (and Back) lead here.
describe("ShortlistView, the way to an option card", () => {
  it("carries the shortlist as the card's origin on its option links", async () => {
    const user = userEvent.setup();
    renderShortlist();
    const link = screen.getAllByRole("link").find((anchor) => anchor.getAttribute("href")?.includes("/options/")) as HTMLElement;
    cleanup();
    function Probe() {
      return <p data-testid="probe">{JSON.stringify(useLocation().state)}</p>;
    }
    const href = link.getAttribute("href") ?? "";
    render(
      <PublicViewProvider value={false}>
        <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
          <Routes>
            <Route path="/tasks/:taskId/result" element={<ShortlistView taskId={TASK_ID} longlist={mockLonglist()} />} />
            <Route path="/tasks/:taskId/options/:optionId" element={<Probe />} />
          </Routes>
        </MemoryRouter>
      </PublicViewProvider>,
    );
    await user.click(screen.getAllByRole("link").find((anchor) => anchor.getAttribute("href") === href) as HTMLElement);
    expect(screen.getByTestId("probe")).toHaveTextContent(JSON.stringify(CARD_FROM_SHORTLIST));
  });
});
