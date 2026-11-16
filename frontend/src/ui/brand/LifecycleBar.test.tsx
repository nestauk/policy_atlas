import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { lifecycleTabs } from "../../views/lifecycle";
import { LifecycleBar } from "./LifecycleBar";

// Owner, round 14: the Result tab is current on every Result route, the
// option cards included, its rule full as on any active tab.
describe("LifecycleBar — the Result tab's routes", () => {
  const renderAt = (path: string) =>
    render(
      <MemoryRouter initialEntries={[path]}>
        <LifecycleBar hint="Available once the analysis has run" items={lifecycleTabs("/tasks/t1", "succeeded")} />
      </MemoryRouter>,
    );

  it.each(["/tasks/t1/result", "/tasks/t1/result?view=longlist", "/tasks/t1/options/o1"])(
    "keeps Result current on %s",
    (path) => {
      renderAt(path);
      const result = screen.getByRole("link", { name: "Result" });
      expect(result).toHaveAttribute("aria-current", "page");
      expect(screen.getByRole("link", { name: "Sources" })).not.toHaveAttribute("aria-current");
    },
  );

  it("gives the option card's Result tab the same active classes as on the Result page", () => {
    renderAt("/tasks/t1/result");
    const onResult = screen.getByRole("link", { name: "Result" }).className;
    renderAt("/tasks/t1/options/o1");
    const links = screen.getAllByRole("link", { name: "Result" });
    expect(links.at(-1)?.className).toBe(onResult);
  });
});
