import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { PageBackLink, PageHeader, PagePrimary, PAGE_CONTROL_CLASS } from "./PageHeader";

function renderHeader(props: Partial<Parameters<typeof PageHeader>[0]> = {}) {
  return render(
    <MemoryRouter>
      <PageHeader title="Tasks" actions={<PagePrimary to="/new">New task</PagePrimary>} {...props} />
    </MemoryRouter>,
  );
}

const slot = (container: HTMLElement, name: string) =>
  container.querySelector(`[data-slot="${name}"]`) as HTMLElement;

// Task 058, lists polish: Tasks, Projects and a Project page share one header
// with fixed slots, so nothing in it moves between pages.
describe("PageHeader — fixed slots", () => {
  it("always renders the context row and the 40 px filters row, even when they are empty (lead ruling P5)", () => {
    const { container } = renderHeader();
    expect(slot(container, "context")).toHaveClass("h-6");
    expect(slot(container, "context")).toBeEmptyDOMElement();
    expect(slot(container, "filters")).toHaveClass("min-h-10");
  });

  it("gives the actions a 52 px row of their own, independent of the title's height", () => {
    const { container } = renderHeader();
    expect(slot(container, "actions")).toHaveClass("h-13");
  });

  it("keeps the title's line box while its text is on its way", () => {
    renderHeader({ title: "" });
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toBeEmptyDOMElement();
    expect(heading).toHaveClass("min-h-[1lh]");
  });

  it("drops the title from Display to Title below md", () => {
    renderHeader();
    expect(screen.getByRole("heading", { name: "Tasks" })).toHaveClass("text-display", "max-md:text-title");
  });

  it("puts the title before the actions in reading order", () => {
    renderHeader({ context: <PageBackLink to="/projects">← Projects</PageBackLink> });
    const order = [
      screen.getByRole("link", { name: "← Projects" }),
      screen.getByRole("heading", { name: "Tasks" }),
      screen.getByRole("link", { name: "New task" }),
    ];
    for (let index = 1; index < order.length; index += 1) {
      expect(order[index - 1].compareDocumentPosition(order[index]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it("renders filters on the left and the aside on the right of one row", () => {
    const { container } = renderHeader({ filters: <span>Mine</span>, aside: <span>Note</span> });
    const filters = slot(container, "filters");
    expect(filters).toHaveTextContent("MineNote");
    expect(screen.getByText("Note").parentElement).toHaveClass("ml-auto");
  });
});

describe("PagePrimary — one primary, built one way", () => {
  it("styles the link and the button identically: 52 px, at least 144 px, never wrapped, the cut, the press", () => {
    const onClick = vi.fn();
    render(
      <MemoryRouter>
        <PagePrimary to="/new">New task</PagePrimary>
        <PagePrimary onClick={onClick}>New project</PagePrimary>
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: "New task" });
    const button = screen.getByRole("button", { name: "New project" });
    expect(link.className).toBe(button.className);
    expect(link).toHaveClass("h-13", "min-w-36", "whitespace-nowrap", "cutout", "pressable", "bg-blue");
  });

  it("stays in place, disabled, when asked", async () => {
    const onClick = vi.fn();
    render(
      <PagePrimary onClick={onClick} disabled>
        New project
      </PagePrimary>,
    );
    const button = screen.getByRole("button", { name: "New project" });
    expect(button).toBeDisabled();
    expect(button).toHaveClass("disabled:bg-line-2");
    await userEvent.setup().click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("header controls", () => {
  it("are 40 px at Body size, the primary's label size", () => {
    expect(PAGE_CONTROL_CLASS).toContain("h-10");
    expect(PAGE_CONTROL_CLASS).toContain("text-body");
    expect(PAGE_CONTROL_CLASS).not.toContain("text-meta");
    render(
      <MemoryRouter>
        <PagePrimary to="/new">New task</PagePrimary>
        <Button variant="ghost" className={PAGE_CONTROL_CLASS}>
          Find a task
        </Button>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "New task" })).toHaveClass("text-body");
    const find = screen.getByRole("button", { name: "Find a task" });
    expect(find).toHaveClass("text-body", "font-semibold", "h-10");
    expect(find).not.toHaveClass("text-meta");
  });

  it("the back link is a 40 px target drawn in the 24 px context row", () => {
    render(
      <MemoryRouter>
        <PageBackLink to="/projects">← Projects</PageBackLink>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "← Projects" })).toHaveClass("h-10", "-my-2", "text-meta", "font-semibold");
  });
});
