import { act, render, renderHook } from "@testing-library/react";
import { memo, useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import type { RunStreamState } from "../store";
import type { DraftRun } from "./ArtefactView";
import { LiveArtefactBody, sameParagraph, SettledParagraph } from "./ArtefactView";

/** A stream writing one section with `draft` so far. */
function streamOf(draft: string): RunStreamState {
  return {
    ...createInitialRunStreamState(),
    run: { id: "r1", status: "running", startedAt: "2026-11-05T10:00:00Z" },
    liveSections: { 1: { index: 1, title: "Costs", focus: "", state: "writing", draft } },
  };
}
import {
  REVEAL_BASE_RATE,
  REVEAL_CATCH_UP_MS,
  REVEAL_IDLE_FLUSH_MS,
  useFollowTail,
  useRevealedText,
  wordBoundary,
} from "./streamPacing";

const WORDS = Array.from({ length: 200 }, (_, at) => `word${at}`).join(" ") + " ";

function fakeFrames() {
  vi.useFakeTimers({
    toFake: ["requestAnimationFrame", "cancelAnimationFrame", "setTimeout", "clearTimeout", "performance", "Date"],
  });
}

/** Advance the clock a frame at a time. */
function frames(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

describe("useRevealedText (task 058, owner round 7: paced streaming)", () => {
  beforeEach(fakeFrames);
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows text already there when the section mounts at once", () => {
    const { result } = renderHook(() => useRevealedText("Cost is the barrier. "));
    expect(result.current.text).toBe("Cost is the barrier. ");
  });

  it("reveals a burst at a steady rate, whole words only, and catches up within the window", () => {
    const { result, rerender } = renderHook(({ draft }) => useRevealedText(draft), { initialProps: { draft: "" } });
    rerender({ draft: WORDS });
    expect(result.current.text).toBe("");
    const seen: number[] = [];
    for (let frame = 0; frame < 20; frame += 1) {
      frames(16);
      seen.push(result.current.text.length);
      // Snapped to the end of a whole word: never half a word.
      if (result.current.text !== "") expect(result.current.text.endsWith(" ")).toBe(true);
    }
    // It grows every few frames, never in one jump.
    expect(seen.at(-1)).toBeGreaterThan(0);
    expect(seen.at(-1)).toBeLessThan(WORDS.length);
    const steps = seen.slice(1).map((length, at) => length - seen[at]);
    expect(Math.max(...steps)).toBeLessThan(WORDS.length / 4);
    // The backlog shrinks by about two thirds a window, then finishes at
    // the base rate: a burst never waits long behind the stream.
    const before = WORDS.length - result.current.text.length;
    frames(REVEAL_CATCH_UP_MS);
    expect(WORDS.length - result.current.text.length).toBeLessThan(before * 0.45);
    frames(4 * REVEAL_CATCH_UP_MS);
    expect(result.current.text).toBe(WORDS);
  });

  it("never drops below the base rate on a small backlog", () => {
    const { result, rerender } = renderHook(({ draft }) => useRevealedText(draft), { initialProps: { draft: "" } });
    const short = "One two three four five six. ";
    rerender({ draft: short });
    frames(Math.ceil(short.length / REVEAL_BASE_RATE) + 32);
    expect(result.current.text).toBe(short);
  });

  it("holds a trailing half-word until its space arrives, or until the draft goes quiet", () => {
    const { result, rerender } = renderHook(({ draft }) => useRevealedText(draft), { initialProps: { draft: "" } });
    rerender({ draft: "Cost is the barr" });
    frames(200);
    expect(result.current.text).toBe("Cost is the ");
    rerender({ draft: "Cost is the barrier families name. " });
    frames(400);
    expect(result.current.text).toBe("Cost is the barrier families name. ");
    rerender({ draft: "Cost is the barrier families name. Fees" });
    frames(REVEAL_IDLE_FLUSH_MS + 50);
    expect(result.current.text).toBe("Cost is the barrier families name. Fees");
  });

  it("cuts back at once, in the same render, when a revision replaces the draft", () => {
    const { result, rerender } = renderHook(({ draft }) => useRevealedText(draft), {
      initialProps: { draft: "Two studies found no effect. More text follows here. " },
    });
    rerender({ draft: "Two studies found none. " });
    // No frame shows text that is gone.
    expect(result.current.text).toBe("Two studies found ");
    frames(200);
    expect(result.current.text).toBe("Two studies found none. ");
  });

  it("shows everything when the section or the run ends", () => {
    const { result, rerender } = renderHook(({ draft, complete }) => useRevealedText(draft, complete), {
      initialProps: { draft: "", complete: false },
    });
    rerender({ draft: WORDS, complete: false });
    frames(16);
    rerender({ draft: WORDS, complete: true });
    expect(result.current.text).toBe(WORDS);
  });

  it("finds the end of the last whole word", () => {
    const chars = Array.from("ab cd ef");
    expect(wordBoundary(chars, chars.length)).toBe(6);
    expect(wordBoundary(chars, 4)).toBe(3);
    expect(wordBoundary(chars, 2)).toBe(0);
  });
});

describe("the live paragraph's words fade in, a batch at a time", () => {
  beforeEach(fakeFrames);
  afterEach(() => {
    vi.useRealTimers();
  });

  function Live({ draft }: { draft: string }) {
    return <LiveArtefactBody stream={streamOf(draft)} />;
  }

  it("wraps each frame's batch in one fading span, and drops them when the paragraph settles", () => {
    const { rerender, container } = render(<Live draft="Cost " />);
    rerender(<Live draft="Cost is the barrier families name most often. " />);
    frames(48);
    const fading = container.querySelectorAll(".anim-word-in");
    expect(fading.length).toBeGreaterThan(0);
    // One span per batch, not one per word.
    const words = [...fading].map((span) => (span.textContent ?? "").trim().split(/\s+/).length);
    expect(Math.max(...words)).toBeGreaterThan(0);
    expect(fading.length).toBeLessThan(10);
    // A new paragraph: the first one settles into plain text, no spans.
    rerender(<Live draft={"Cost is the barrier families name most often.\n\nSubsidy design matters more than its size. "} />);
    frames(2000);
    const paragraph = container.querySelector("[data-testid='draft-prose'] p") as HTMLElement;
    const settledText = "Cost is the barrier families name most often.";
    const settled = [...paragraph.querySelectorAll(".anim-word-in")].filter((span) =>
      settledText.includes((span.textContent ?? "").trim()),
    );
    expect(settled.filter((span) => (span.textContent ?? "").trim() !== "")).toHaveLength(0);
  });
});

describe("settled paragraphs are frozen", () => {
  const runs = (text: string): DraftRun[] => [{ text, start: 0, revising: false }];

  it("is a memo whose comparator looks at the text, the repair spans and the marks", () => {
    expect((SettledParagraph as unknown as { compare: unknown }).compare).toBe(sameParagraph);
    expect(sameParagraph({ runs: runs("Cost is the barrier.") }, { runs: runs("Cost is the barrier.") })).toBe(true);
    expect(sameParagraph({ runs: runs("Cost is the barrier.") }, { runs: runs("Cost is the barrier") })).toBe(false);
    expect(
      sameParagraph({ runs: runs("Cost.") }, { runs: [{ text: "Cost.", start: 0, revising: true }] }),
    ).toBe(false);
    const mark = { start: 0, end: 5, sources: [{ sourceId: "a", title: "Smith 2023" }] };
    expect(
      sameParagraph(
        { runs: [{ text: "Cost.", start: 0, revising: false, marks: [mark] }] },
        { runs: [{ text: "Cost.", start: 0, revising: false, marks: [{ ...mark, sources: [...mark.sources] }] }] },
      ),
    ).toBe(true);
    expect(sameParagraph({ runs: runs("Cost.") }, { runs: [{ text: "Cost.", start: 0, revising: false, marks: [mark] }] })).toBe(
      false,
    );
  });

  it("does not re-render a settled paragraph when only the tail grows", () => {
    const rendered = vi.fn();
    function Counting({ runs: paragraph }: { runs: DraftRun[] }) {
      rendered();
      return <span>{paragraph[0].text}</span>;
    }
    const Frozen = memo(Counting, sameParagraph);
    const { rerender } = render(<Frozen runs={runs("First paragraph.")} />);
    rerender(<Frozen runs={runs("First paragraph.")} />);
    expect(rendered).toHaveBeenCalledTimes(1);
    rerender(<Frozen runs={runs("First paragraph, changed.")} />);
    expect(rendered).toHaveBeenCalledTimes(2);
  });
});

describe("useFollowTail: the scroll rule", () => {
  let resize: () => void = () => undefined;
  beforeEach(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        constructor(callback: () => void) {
          resize = callback;
        }
        observe() {}
        disconnect() {}
      },
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function Page({ active }: { active: boolean }) {
    const anchor = useRef<HTMLSpanElement>(null);
    useFollowTail(anchor, active);
    return (
      <div data-testid="pane" style={{ overflowY: "auto" }}>
        <main>
          <span ref={anchor} />
        </main>
      </div>
    );
  }

  /** Give the pane a size and a scroll position (jsdom lays nothing out). */
  function size(pane: HTMLElement, { height, top }: { height: number; top: number }) {
    Object.defineProperty(pane, "scrollHeight", { configurable: true, value: height });
    Object.defineProperty(pane, "clientHeight", { configurable: true, value: 500 });
    pane.scrollTop = top;
  }

  it("follows a reader within 40 px of the end, and stops on the first scroll upwards", () => {
    const { getByTestId, rerender } = render(<Page active={false} />);
    const pane = getByTestId("pane");
    size(pane, { height: 2000, top: 1480 });
    rerender(<Page active />);
    size(pane, { height: 2100, top: 1480 });
    resize();
    expect(pane.scrollTop).toBe(2100);
    // The reader scrolls up: they are left where they are from now on.
    pane.scrollTop = 1200;
    pane.dispatchEvent(new Event("scroll"));
    size(pane, { height: 2300, top: 1200 });
    resize();
    expect(pane.scrollTop).toBe(1200);
  });

  it("never moves a reader who is higher up the page", () => {
    const { getByTestId, rerender } = render(<Page active={false} />);
    const pane = getByTestId("pane");
    size(pane, { height: 2000, top: 600 });
    rerender(<Page active />);
    size(pane, { height: 2400, top: 600 });
    resize();
    expect(pane.scrollTop).toBe(600);
  });
});
