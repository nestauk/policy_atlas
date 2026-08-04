import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CheckInBundle, proposedSections } from "./CheckInBundle";

function renderBundle(
  bundle: Record<string, unknown>,
  overrides: Partial<React.ComponentProps<typeof CheckInBundle>> = {},
) {
  const onStageRename = vi.fn();
  const onEditSections = vi.fn();
  render(
    <CheckInBundle
      bundle={bundle}
      stagedRenames={[]}
      onStageRename={onStageRename}
      editedSections={null}
      onEditSections={onEditSections}
      {...overrides}
    />,
  );
  return { onStageRename, onEditSections };
}

describe("CheckInBundle", () => {
  it("renders the P1 search-review bundle: backend counts, sample titles, queries", () => {
    renderBundle({
      backends: [{ backend: "OpenAlex", count: 41 }, { backend: "Overton", count: 23 }],
      queries: ["childhood obesity local policy"],
      sample_titles: ["Free childcare: why, who for and how?"],
    });
    expect(screen.getByText(/OpenAlex 41 · Overton 23 · from 1 query/)).toBeInTheDocument();
    expect(screen.getByText("Free childcare: why, who for and how?")).toBeInTheDocument();
  });

  it("P2 themes render with counts and rename stages a card-local edit", async () => {
    const user = userEvent.setup();
    const { onStageRename } = renderBundle({
      themes: [{ theme_id: "t-1", name: "Workforce capacity", size: 6 }],
    });
    await user.click(screen.getByRole("button", { name: "Rename Workforce capacity" }));
    const input = screen.getByLabelText("New name for Workforce capacity");
    await user.clear(input);
    await user.type(input, "Workforce pay and quality");
    await user.click(screen.getByRole("button", { name: "Rename" }));
    expect(onStageRename).toHaveBeenCalledWith({
      theme_id: "t-1",
      name: "Workforce pay and quality",
    });
  });

  it("themes without theme_id render read-only (no rename affordance)", () => {
    renderBundle({ themes: [{ theme_id: null, name: "Legacy theme", size: 3 }] });
    expect(screen.getByText("Legacy theme")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Rename/ })).toBeNull();
  });

  it("P4 rows edit in place: × removes and reports the full edited list", async () => {
    const user = userEvent.setup();
    const { onEditSections } = renderBundle({
      proposal: {
        proposed_sections: [
          { title: "What the evidence shows", focus: "Answer the question" },
          { title: "Delivery barriers", focus: "Barriers reported" },
        ],
      },
    });
    await user.click(screen.getByRole("button", { name: "Remove section Delivery barriers" }));
    expect(onEditSections).toHaveBeenCalledWith([
      { title: "What the evidence shows", focus: "Answer the question" },
    ]);
  });

  it("proposedSections parses the P4 bundle fail-soft", () => {
    expect(proposedSections({ proposal: { proposed_sections: [{ title: "A", focus: "B" }, { bad: true }] } })).toEqual([
      { title: "A", focus: "B" },
    ]);
    expect(proposedSections(null)).toEqual([]);
  });
});
