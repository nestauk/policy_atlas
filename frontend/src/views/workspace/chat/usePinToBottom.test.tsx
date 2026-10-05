import { useRef } from "react";
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { JumpToEnd } from "./JumpToEnd";
import { usePinToBottom } from "./usePinToBottom";

function Pane({ chatId }: { chatId: string }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const pin = usePinToBottom(scrollRef, contentRef, chatId);
  return (
    <div className="relative">
      <div ref={scrollRef} data-testid="scroll" onScroll={pin.onScroll}>
        <div ref={contentRef}>transcript</div>
      </div>
      <JumpToEnd visible={!pin.atEnd} onClick={pin.jumpToEnd} />
    </div>
  );
}

describe("usePinToBottom", () => {
  it("opens a transcript at its end, and again when the conversation changes", () => {
    // jsdom has no layout: give the scroll region a tall content height.
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", { configurable: true, value: 4000 });
    Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 600 });
    const { getByTestId, rerender } = render(<Pane chatId="c-1" />);
    const scroll = getByTestId("scroll");
    expect(scroll.scrollTop).toBe(4000);

    scroll.scrollTop = 0; // the reader goes to the top
    rerender(<Pane chatId="c-2" />); // another chat opens
    expect(scroll.scrollTop).toBe(4000);
  });

  it("offers the way back once the reader scrolls up, and jumps to the end", () => {
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", { configurable: true, value: 4000 });
    Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 600 });
    const { getByTestId, getByTitle } = render(<Pane chatId="c-1" />);
    const scroll = getByTestId("scroll");
    expect(getByTitle("Jump to the end")).toHaveAttribute("aria-hidden", "true");

    scroll.scrollTop = 0;
    fireEvent.scroll(scroll);
    const button = getByTitle("Jump to the end");
    expect(button).toHaveAttribute("aria-hidden", "false");

    scroll.scrollTo = () => {
      scroll.scrollTop = 4000;
    };
    fireEvent.click(button);
    expect(scroll.scrollTop).toBe(4000);
    expect(button).toHaveAttribute("aria-hidden", "true");
  });
});
