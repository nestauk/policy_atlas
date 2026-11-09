import { render, screen } from "@testing-library/react";
import { useRef } from "react";
import { describe, expect, it } from "vitest";

import { useOpenAtTop } from "./openAtTop";

function Page({ view }: { view: string }) {
  const titleRef = useRef<HTMLHeadingElement>(null);
  useOpenAtTop(titleRef, view);
  return (
    <h1 ref={titleRef} tabIndex={-1}>
      {view}
    </h1>
  );
}

// Round 13 (owner): a Result-tab switch opens the page at its top, focus on
// its title, once per view; a later render leaves the reader where they are.
describe("useOpenAtTop", () => {
  it("scrolls the pane to the top and focuses the title, once per view", () => {
    const tree = (view: string) => (
      <div data-testid="pane" style={{ overflowY: "auto" }}>
        <Page view={view} />
      </div>
    );
    const { rerender } = render(<div data-testid="pane" style={{ overflowY: "auto" }} />);
    const pane = screen.getByTestId("pane");
    pane.scrollTop = 900;
    rerender(tree("longlist"));
    expect(screen.getByTestId("pane").scrollTop).toBe(0);
    expect(screen.getByRole("heading", { name: "longlist" })).toHaveFocus();
    screen.getByTestId("pane").scrollTop = 400;
    rerender(tree("longlist"));
    expect(screen.getByTestId("pane").scrollTop).toBe(400);
    rerender(tree("shortlist"));
    expect(screen.getByTestId("pane").scrollTop).toBe(0);
  });
});
