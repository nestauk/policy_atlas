import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ListFootRow, Pagination, ShowMore } from "./ListFoot";
import { LIST_FRAME_CLASS, ListEmpty, ListError, ListSkeleton } from "./ListStates";

describe("ListFootRow", () => {
  it("is nothing when it has neither end", () => {
    const { container } = render(<ListFootRow start={null} end={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("puts its start at the left and its end's items in one row at the right", () => {
    render(<ListFootRow data-testid="foot" start={<span>Start</span>} end={<><span>A</span><span>B</span></>} />);
    const foot = screen.getByTestId("foot");
    expect(foot.firstElementChild).toHaveTextContent("Start");
    const end = foot.lastElementChild as HTMLElement;
    expect(end).toHaveClass("ml-auto", "flex");
    expect([...end.children].map((child) => child.textContent)).toEqual(["A", "B"]);
  });
});

describe("ShowMore", () => {
  it("holds its place, disabled and busy, while the next page loads", async () => {
    const onShowMore = vi.fn();
    const { rerender } = render(<ShowMore loading={false} onShowMore={onShowMore} />);
    await userEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(onShowMore).toHaveBeenCalledTimes(1);
    rerender(<ShowMore loading onShowMore={onShowMore} />);
    expect(screen.getByRole("button", { name: "Show more" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Show more" })).toHaveAttribute("aria-busy", "true");
  });
});

describe("Pagination", () => {
  it("names the page in tabular figures and stops at either end", async () => {
    const onPage = vi.fn();
    render(<Pagination page={1} totalPages={1200} onPage={onPage} />);
    const pages = screen.getByRole("navigation", { name: "Pages" });
    expect(pages).toHaveTextContent("Page 1 of 1,200");
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onPage).toHaveBeenCalledWith(2);
  });
});

describe("the list's frames", () => {
  it("draws the empty list in the lists' frame, a label then one sentence", () => {
    render(<ListEmpty label="No tasks yet">Tasks you start appear here.</ListEmpty>);
    const frame = screen.getByRole("status");
    expect(frame).toHaveClass(...LIST_FRAME_CLASS.split(" "));
    expect(frame).toHaveTextContent("No tasks yetTasks you start appear here.");
  });

  it("takes a surface's own frame and a way out at its right", () => {
    render(<ListEmpty label="No sources match" frameClassName="sources-frame" action={<button type="button">Clear filters</button>} />);
    const frame = screen.getByRole("status");
    expect(frame).toHaveClass("sources-frame");
    expect(frame).not.toHaveClass("border-line-2");
    expect(frame.lastElementChild).toHaveTextContent("Clear filters");
  });

  it("says what failed and asks again with the 40 px ghost", async () => {
    const onRetry = vi.fn();
    render(<ListError actionLabel="Try again" onRetry={onRetry}>Sources couldn't be loaded.</ListError>);
    expect(screen.getByRole("alert")).toHaveTextContent("Sources couldn't be loaded.");
    const retry = screen.getByRole("button", { name: "Try again" });
    expect(retry).toHaveClass("h-10");
    await userEvent.click(retry);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("loads in the list's frame and row shape", () => {
    render(<ListSkeleton label="Loading tasks" />);
    const list = screen.getByRole("list", { name: "Loading tasks" });
    expect(list).toHaveAttribute("aria-busy", "true");
    expect(list.children).toHaveLength(5);
  });
});
