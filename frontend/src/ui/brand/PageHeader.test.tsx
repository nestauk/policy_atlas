import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { PageBackLink, PageHeader, PagePrimary } from "./PageHeader";

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
  it("always renders the context row and the filters row, even when they are empty", () => {
    const { container } = renderHeader();
    expect(slot(container, "context")).toBeEmptyDOMElement();
    expect(slot(container, "filters")).toBeInTheDocument();
  });

  it("keeps the title heading while its text is on its way", () => {
    renderHeader({ title: "" });
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toBeEmptyDOMElement();
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
  });
});

describe("PagePrimary — one primary, built one way", () => {
  it("stays in place, disabled, when asked", async () => {
    const onClick = vi.fn();
    render(
      <PagePrimary onClick={onClick} disabled>
        New project
      </PagePrimary>,
    );
    const button = screen.getByRole("button", { name: "New project" });
    expect(button).toBeDisabled();
    await userEvent.setup().click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});
