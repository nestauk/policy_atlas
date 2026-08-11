import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "../../../ui/radix/Tooltip";

import type { ChatConversationRow, ChatTurn, OptimisticChatTurn } from "../../../store";
import { ChatMessages } from "./ChatMessages";

// The citation sheet's quote-in-context fetch is the only place this view
// calls the API client — mock just that hook (029 Fix A/B) so a click on a
// marker/reference resolves without a real network/auth stack.
const mockGet = vi.fn();
vi.mock("../../../api/queries", async () => {
  const actual = await vi.importActual<typeof import("../../../api/queries")>("../../../api/queries");
  return { ...actual, useApiClient: () => ({ GET: mockGet }) };
});

beforeEach(() => {
  mockGet.mockReset();
});

function turn(overrides: Partial<ChatTurn> = {}): ChatTurn {
  // `state: "verdict:<tier>"` is the only shape the floor's allowlist can
  // ever emit — a bare `grounding_tier`/`verdict` key on the citation is
  // dead-payload territory (ChatMessages no longer reads it).
  return { id: "t1", client_turn_id: "ct1", conversation_id: "c1", turn_index: 0, created_at: "2026-08-11T10:00:00Z", completed_at: "2026-08-11T10:01:00Z", user_message: "What changed?", answer: "Costs fell [1]", status: "completed", stopped_before_evidence_check: false, warning_not_evidence_checked: false, citations: [{ id: "chunk-1", n: 1, quote: "Costs fell", state: "verdict:tier_2" }], claims: [], ...overrides };
}

function optimisticTurn(overrides: Partial<OptimisticChatTurn> = {}): OptimisticChatTurn {
  return { clientTurnId: "ct-opt", userMessage: "What does the evidence say?", createdAt: "2026-08-11T10:00:00Z", answer: "", status: "pending", activityLabels: [], ...overrides };
}

function renderChat(rows: ChatConversationRow[], props: { onOpenPlanning?: () => void; onRetry?: (clientTurnId: string) => void } = {}) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <ChatMessages projectId="p1" rows={rows} onOpenPlanning={props.onOpenPlanning ?? vi.fn()} onRetry={props.onRetry ?? vi.fn()} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

/** Every References disclosure on the page starts collapsed (029 Fix D) —
 *  open them all so a test can assert on what they contain. */
async function openAllReferences() {
  const user = userEvent.setup();
  for (const summary of screen.getAllByText(/^References \(\d+\)$/)) {
    await user.click(summary);
  }
  return user;
}

describe("ChatMessages", () => {
  it("renders citation markers, references, verdicts, warnings and handoff", async () => {
    const openPlanning = vi.fn();
    renderChat([turn({ warning_not_evidence_checked: true, handoff: "evidence_not_held" }), turn({ id: "t2", client_turn_id: "ct2", status: "cancelled", stopped_before_evidence_check: true, answer: "Partial" })], { onOpenPlanning: openPlanning });
    await openAllReferences();
    expect(screen.getAllByRole("button", { name: "[1]" })).not.toHaveLength(0);
    expect(screen.getAllByText("Tier 2 · grounded").length).toBeGreaterThan(0);
    expect(screen.getByText("Not evidence-checked")).toBeInTheDocument();
    expect(screen.getByText("Stopped before evidence check")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Open planning" }));
    expect(openPlanning).toHaveBeenCalledOnce();
  });

  it("shows an unresolved citation as unchecked and a failed one as flagged", async () => {
    renderChat([turn({ id: "t3", client_turn_id: "ct3", answer: "Costs fell [1] and uptake held [2]", citations: [{ id: "chunk-1", n: 1, quote: "Costs fell" }, { id: "chunk-2", n: 2, quote: "Uptake held", state: "verdict:unsupported_mis_cited" }] })]);
    await openAllReferences();
    expect(screen.getByText("Unchecked · awaiting evidence check")).toBeInTheDocument();
    expect(screen.getByText("Unsupported — flagged")).toBeInTheDocument();
  });

  it("ignores a bare grounding_tier/verdict key on the citation itself (dead payload shape)", async () => {
    renderChat([turn({ id: "t3b", client_turn_id: "ct3b", answer: "Costs fell [1]", citations: [{ id: "chunk-1", n: 1, quote: "Costs fell", grounding_tier: "tier_2", verdict: "tier_2" }] })]);
    await openAllReferences();
    expect(screen.getByText("Unchecked · awaiting evidence check")).toBeInTheDocument();
    expect(screen.queryByText("Tier 2 · grounded")).not.toBeInTheDocument();
  });

  it("renders a still-streaming optimistic turn's activity summary and partial prose", () => {
    renderChat([optimisticTurn({ activityLabels: ["Searching sources", "Reading passages"], answer: "Costs fell so " })]);
    expect(screen.getByText("Reading passages — 2 searches")).toBeInTheDocument();
    expect(screen.getByText("Costs fell so", { exact: false })).toBeInTheDocument();
  });

  it("renders a failed turn honestly with a known conflict sentence and a wired retry", async () => {
    const onRetry = vi.fn();
    renderChat([optimisticTurn({ status: "failed", errorCode: "chat_turn_in_progress", errorMessage: "a chat turn is already running" })], { onRetry });
    expect(screen.getByRole("alert")).toHaveTextContent("A chat turn is already running. Refresh to see it finish.");
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledWith("ct-opt");
  });

  it("falls back to a generic honest sentence for an unrecognised or durable (code-less) failure", () => {
    renderChat([turn({ id: "t4", client_turn_id: "ct4", status: "failed", answer: null })]);
    expect(screen.getByRole("alert")).toHaveTextContent("This answer failed.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("keeps References collapsed by default and expands to reveal its verdict chips (029 Fix D)", async () => {
    renderChat([turn()]);
    // jsdom does not apply the browser's default closed-<details> hiding, so
    // the `open` attribute — not text visibility — is the authoritative,
    // browser-accurate signal that the disclosure starts collapsed.
    const details = screen.getByText("References (1)").closest("details");
    expect(details).not.toHaveAttribute("open");
    await userEvent.setup().click(screen.getByText("References (1)"));
    expect(details).toHaveAttribute("open");
    expect(screen.getByText("Tier 2 · grounded")).toBeInTheDocument();
  });

  it("opens the citation sheet from an inline marker with the citing claim text and the highlighted context (029 Fix B)", async () => {
    mockGet.mockResolvedValueOnce({
      data: { context: "Costs fell sharply last year.", previous: "An intro sentence.", next: "A trailing sentence.", year: 2024, venue: "Journal of Policy" },
      error: undefined,
    });
    renderChat([turn({ claims: [{ claim_id: "c1", text: "Costs fell sharply.", citation_ns: [1], verdict: "tier_2", rationale: "Matches the source passage." }] })]);
    const [marker] = screen.getAllByRole("button", { name: "[1]" });
    await userEvent.setup().click(marker);
    expect(screen.getByText("Where this comes from")).toBeInTheDocument();
    expect(screen.getByText("Costs fell sharply.")).toBeInTheDocument();
    expect(await screen.findByText(/sharply last year/)).toBeInTheDocument();
    expect(screen.getByText("An intro sentence.")).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("shows the honest not-found line immediately on a 404, without retrying (029 Fix A)", async () => {
    mockGet.mockResolvedValueOnce({ data: undefined, error: { detail: "not found" } });
    renderChat([turn()]);
    const [marker] = screen.getAllByRole("button", { name: "[1]" });
    await userEvent.setup().click(marker);
    expect(await screen.findByText("Exact passage not found in the source — showing the cited quote.")).toBeInTheDocument();
    expect(screen.getByText("“Costs fell”")).toBeInTheDocument();
    // TanStack's default retries 3 times on failure — retry:false means this
    // 404 produces exactly one call, not a multi-second retry storm.
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("keeps a cancelled turn's inline markers inert — clickable but no verdict tooltip promised", async () => {
    renderChat([turn({ id: "t5", client_turn_id: "ct5", status: "cancelled", stopped_before_evidence_check: true })]);
    const [marker] = screen.getAllByRole("button", { name: "[1]" });
    expect(marker).toBeDisabled();
  });

  // 030 fold: chat's answer prose becomes claim-span annotated, mirroring
  // the report reader's own claim-span affordance (same citation-marker
  // class, same click/Enter/Space-opens-a-sheet grain) — a distinct entry
  // point from the literal `[n]` marker button, which keeps its 029 Fix C
  // behaviour untouched.
  it("renders a claim span with the report's citation-marker treatment, opening a claim-oriented sheet over the claim's cited source (030 fold)", async () => {
    mockGet.mockResolvedValueOnce({
      data: { context: "Costs fell sharply overall.", year: 2024, venue: "Journal of Policy" },
      error: undefined,
    });
    const spanText = "Costs fell sharply";
    renderChat([
      turn({
        answer: `${spanText} [1] this year.`,
        citations: [{ id: "chunk-1", n: 1, quote: "Costs fell sharply", source_title: "A breakfast study", state: "verdict:tier_2" }],
        claims: [{ claim_id: "c1", text: spanText, span: [0, spanText.length], citation_ns: [1], verdict: "tier_2" }],
      }),
    ]);
    const span = screen.getByRole("button", { name: spanText });
    expect(span.className).toContain("citation-marker");
    // The literal `[1]` marker stays its own, separate, small button (the
    // References row below carries a second one) — the span wraps only the
    // claim's own text, not the trailing marker.
    expect(screen.getAllByRole("button", { name: "[1]" })).toHaveLength(2);
    await userEvent.setup().click(span);
    const sheet = screen.getByRole("dialog", { name: "Where this comes from" });
    // Appears twice: the claim-text blockquote, and again inside the
    // highlighted quote-in-context below it.
    expect(within(sheet).getAllByText(spanText)).toHaveLength(2);
    expect(within(sheet).getByRole("button", { name: "A breakfast study" })).toBeInTheDocument();
    expect(await within(sheet).findByText(/overall/)).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("opens a claim span with Enter from the keyboard, same as a click", async () => {
    mockGet.mockResolvedValueOnce({ data: { context: "context text", year: 2024 }, error: undefined });
    const spanText = "Costs fell sharply";
    renderChat([
      turn({
        answer: `${spanText} [1] this year.`,
        citations: [{ id: "chunk-1", n: 1, quote: "Costs fell sharply", source_title: "A breakfast study" }],
        claims: [{ claim_id: "c1", text: spanText, span: [0, spanText.length], citation_ns: [1] }],
      }),
    ]);
    const span = screen.getByRole("button", { name: spanText });
    span.focus();
    await userEvent.setup().keyboard("{Enter}");
    expect(screen.getByRole("dialog", { name: "Where this comes from" })).toBeInTheDocument();
  });

  it("keeps a marker nested inside a claim span opening only its own citation sheet — no double-open from the enclosing span", async () => {
    mockGet.mockResolvedValueOnce({ data: { context: "context text", year: 2024 }, error: undefined });
    const withMarker = "Costs fell sharply [1]";
    renderChat([
      turn({
        answer: `${withMarker} this year.`,
        citations: [{ id: "chunk-1", n: 1, quote: "Costs fell sharply", source_title: "A breakfast study" }],
        claims: [{ claim_id: "c1", text: withMarker, span: [0, withMarker.length], citation_ns: [1] }],
      }),
    ]);
    const [inlineMarker] = screen.getAllByRole("button", { name: "[1]" });
    await userEvent.setup().click(inlineMarker);
    expect(screen.getAllByRole("dialog", { name: "Where this comes from" })).toHaveLength(1);
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("does not annotate a cancelled turn's prose with claim spans — markers alone stay inert", () => {
    const spanText = "Costs fell sharply";
    renderChat([
      turn({
        id: "t6",
        client_turn_id: "ct6",
        status: "cancelled",
        stopped_before_evidence_check: true,
        answer: `${spanText} [1] this year.`,
        claims: [{ claim_id: "c1", text: spanText, span: [0, spanText.length], citation_ns: [1] }],
      }),
    ]);
    expect(screen.queryByRole("button", { name: spanText })).not.toBeInTheDocument();
    const [inlineMarker] = screen.getAllByRole("button", { name: "[1]" });
    expect(inlineMarker).toBeDisabled();
  });
});
