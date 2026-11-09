import { act, render, renderHook } from "@testing-library/react";
import { StrictMode, memo, useRef } from "react";
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
  useEasedHeight,
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

// `useEasedHeight` in jsdom: heights come from a stubbed
// `getBoundingClientRect`, and `animate` records what each box asked for.
// The box eases only what it owes its content (the content's bottom margin,
// from minus the change to nothing), never a fixed height of its own.
type Made = { el: HTMLElement; keyframes: unknown; animation: { cancel: () => void; onfinish: (() => void) | null; cancelled: boolean } };

function stubBoxes(heightOf: (el: HTMLElement) => number) {
  const made: Made[] = [];
  const restoreAnimate = HTMLElement.prototype.animate;
  HTMLElement.prototype.animate = function (this: HTMLElement, keyframes: unknown) {
    const animation = {
      cancelled: false,
      onfinish: null as (() => void) | null,
      cancel() {
        this.cancelled = true;
      },
    };
    made.push({ el: this, keyframes, animation });
    return animation as unknown as Animation;
  } as typeof HTMLElement.prototype.animate;
  const rect = vi
    .spyOn(HTMLElement.prototype, "getBoundingClientRect")
    .mockImplementation(function (this: HTMLElement) {
      return { height: heightOf(this) } as DOMRect;
    });
  return {
    made,
    restore() {
      rect.mockRestore();
      HTMLElement.prototype.animate = restoreAnimate;
    },
  };
}

async function flushMeasures() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

function Lines({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <p key={index}>line</p>
      ))}
    </>
  );
}

describe("useEasedHeight — what it owes", () => {
  function Box({ lines, growOnly = false }: { lines: number; growOnly?: boolean }) {
    const [box, content] = useEasedHeight(true, growOnly);
    return (
      <div ref={box}>
        <div ref={content}>
          <Lines count={lines} />
        </div>
      </div>
    );
  }

  it("holds back what the content grew by and lets it out, with the box clipping meanwhile", async () => {
    let height = 20;
    const stub = stubBoxes(() => height);
    const view = render(<Box lines={1} />);
    height = 40;
    view.rerender(<Box lines={2} />);
    await flushMeasures();
    expect(stub.made.at(-1)?.keyframes).toEqual([{ marginBottom: "-20px" }, { marginBottom: "0px" }]);
    const box = view.container.firstElementChild as HTMLElement;
    expect(stub.made.at(-1)?.el).toBe(box.firstElementChild);
    expect(box.style.overflow).toBe("clip");
    act(() => stub.made.at(-1)?.animation.onfinish?.());
    expect(box.style.overflow).toBe("");
    stub.restore();
  });

  it("gives a shrink back smoothly, or lets it straight through when it eases growth only", async () => {
    let height = 40;
    const stub = stubBoxes(() => height);
    const view = render(<Box lines={2} />);
    height = 20;
    view.rerender(<Box lines={1} />);
    await flushMeasures();
    expect(stub.made.at(-1)?.keyframes).toEqual([{ marginBottom: "20px" }, { marginBottom: "0px" }]);
    view.unmount();
    stub.made.length = 0;
    height = 40;
    const grow = render(<Box lines={2} growOnly />);
    height = 20;
    grow.rerender(<Box lines={1} growOnly />);
    await flushMeasures();
    expect(stub.made).toEqual([]);
    stub.restore();
  });

  it("carries on from what it still owes when the content changes mid-ease", async () => {
    let height = 20;
    const stub = stubBoxes(() => height);
    const view = render(<Box lines={1} />);
    height = 40;
    view.rerender(<Box lines={2} />);
    await flushMeasures();
    // Mid-ease it still owes 15 of the 20 px; another 10 px land.
    const content = view.container.firstElementChild?.firstElementChild as HTMLElement;
    content.style.marginBottom = "-15px";
    height = 50;
    view.rerender(<Box lines={3} />);
    await flushMeasures();
    expect(stub.made.at(-1)?.keyframes).toEqual([{ marginBottom: "-25px" }, { marginBottom: "0px" }]);
    stub.restore();
  });

  it("opens from nothing on mount, and again after a development remount", () => {
    function Opening() {
      const [box, content] = useEasedHeight(true, false, true);
      return (
        <div ref={box}>
          <div ref={content}>
            <Lines count={2} />
          </div>
        </div>
      );
    }
    const stub = stubBoxes(() => 48);
    render(
      <StrictMode>
        <Opening />
      </StrictMode>,
    );
    const live = stub.made.filter((made) => !made.animation.cancelled);
    expect(live.map((made) => made.keyframes)).toEqual([[{ marginBottom: "-48px" }, { marginBottom: "0px" }]]);
    stub.restore();
  });
});

// Round 12: an eased box inside another (a streamed reply in the Task Agent
// thread, inside its turn, inside the thread). Round 14: the outer box is
// created first, but measures after the inner one, so the inner one absorbs
// its change first. Owner, 2026-11-09: the action line under a streaming
// reply dropped out of view, because the turn's box eased to a fixed height,
// froze there while the reply's box grew, and restarted on every word.
describe("useEasedHeight — a box inside another", () => {
  function Inner({ lines }: { lines: number }) {
    const [box, content] = useEasedHeight(true);
    return (
      <div ref={box} data-box="inner">
        <div ref={content} data-content="inner">
          <Lines count={lines} />
        </div>
      </div>
    );
  }
  function Outer({ lines, growOnly = false }: { lines: number; growOnly?: boolean }) {
    const [box, content] = useEasedHeight(true, growOnly);
    return (
      <div ref={box} data-box="outer">
        <div ref={content} data-content="outer">
          <Inner lines={lines} />
          <p>the action line</p>
        </div>
      </div>
    );
  }

  it("leaves a reply's new line to the reply's box and never freezes or restarts around it", async () => {
    // The inner box absorbs its line: until it eases it out, the outer
    // content keeps its old height.
    let innerLines = 1;
    let absorbed = 1;
    const stub = stubBoxes((el) => {
      if (el.dataset.content === "inner") return innerLines * 20;
      if (el.dataset.content === "outer") return absorbed * 20 + 20;
      return 0;
    });
    const view = render(<Outer lines={1} />);
    const animations = () => stub.made.map((made) => (made.el.dataset.content ?? "?") + JSON.stringify(made.keyframes));
    innerLines = 2;
    view.rerender(<Outer lines={2} />);
    await flushMeasures();
    expect(animations()).toEqual(['inner[{"marginBottom":"-20px"},{"marginBottom":"0px"}]']);
    // Frames pass: the inner box lets its line out and the outer content
    // grows with it, with no DOM change; then a word lands that adds no line.
    absorbed = 2;
    view.rerender(<Outer lines={2} />);
    await flushMeasures();
    expect(animations()).toHaveLength(1);
    // Nothing ever animates a box's own height.
    expect(stub.made.every((made) => !JSON.stringify(made.keyframes).includes("height"))).toBe(true);
    stub.restore();
  });

  it("ignores a box inside it clipping or letting go", async () => {
    let outer = 40;
    const stub = stubBoxes((el) => (el.dataset.content === "outer" ? outer : 20));
    const view = render(<Outer lines={1} growOnly />);
    // The inner box's ease finishes after the browser moved the animations
    // on a frame: the outer content reads taller than the outer last saw.
    outer = 46;
    const inner = view.container.querySelector<HTMLElement>('[data-box="inner"]');
    inner?.style.setProperty("overflow", "clip");
    await flushMeasures();
    expect(stub.made).toEqual([]);
    stub.restore();
  });
});
