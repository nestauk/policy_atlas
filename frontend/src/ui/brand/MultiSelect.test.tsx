import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { MultiSelect } from "./MultiSelect";

const OPTIONS = [
  { value: "a", label: "Childhood obesity", sub: "Child health" },
  { value: "b", label: "Housing supply" },
  { value: "c", label: "Housing costs" },
];

function Harness({ initial = [] as string[] }) {
  const [values, setValues] = useState<string[]>(initial);
  return (
    <MultiSelect
      label="Searches"
      options={OPTIONS}
      values={values}
      onChange={setValues}
      placeholder="None"
      filterLabel="Find a search"
      empty="No searches"
    />
  );
}

const trigger = () => screen.getByRole("button", { name: /^Searches:/ });

describe("MultiSelect", () => {
  it("reads the placeholder, then the one name, then how many are chosen", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    expect(trigger()).toHaveTextContent(/^None$/);
    await user.click(trigger());
    await user.click(screen.getByRole("checkbox", { name: /^Childhood obesity/ }));
    expect(trigger()).toHaveTextContent(/^Childhood obesity$/);
    await user.click(screen.getByRole("checkbox", { name: "Housing supply" }));
    expect(trigger()).toHaveTextContent(/^2 selected$/);
  });

  it("opens on a focused filter that narrows the rows, and says when nothing matches", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(trigger());
    const filter = screen.getByRole("searchbox", { name: "Find a search" });
    expect(filter).toHaveFocus();
    await user.type(filter, "hous");
    expect(screen.getAllByRole("checkbox").map((box) => box.textContent)).toEqual(["Housing supply", "Housing costs"]);
    await user.clear(filter);
    await user.type(filter, "zzz");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.getByText("No searches")).toBeInTheDocument();
  });

  it("shows the chosen ones as Navy chips that take themselves out", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["a", "c"]} />);
    const chips = screen.getByRole("list", { name: "Searches: chosen" });
    expect(within(chips).getAllByRole("listitem")[0]).toHaveClass("bg-navy", "text-paper");
    await user.click(screen.getByRole("button", { name: "Remove Childhood obesity" }));
    expect(trigger()).toHaveTextContent(/^Housing costs$/);
    expect(screen.queryByRole("button", { name: "Remove Childhood obesity" })).not.toBeInTheDocument();
  });
});

describe("MultiSelect — disabled", () => {
  it("reads its placeholder in the disabled look and does not open", async () => {
    const user = userEvent.setup();
    render(
      <MultiSelect
        label="Searches"
        options={OPTIONS}
        values={["a"]}
        onChange={() => {}}
        placeholder="Choose a project first"
        filterLabel="Find a search"
        empty="No searches"
        disabled
      />,
    );
    const button = screen.getByRole("button", { name: /^Searches:/ });
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent(/^Choose a project first$/);
    await user.click(button);
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Searches: chosen" })).not.toBeInTheDocument();
  });
});
