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
  it("renders the P1 search-review bundle: public backend labels, not raw keys", () => {
    // Raw lowercase keys, as the stream/bundle actually carries them — a
    // display-cased fixture here previously masked the raw-key defect.
    renderBundle({
      backends: [{ backend: "openalex", count: 41 }, { backend: "overton", count: 23 }],
      queries: ["childhood obesity local policy"],
      sample_titles: ["Free childcare: why, who for and how?"],
    });
    expect(
      screen.getByText(/OpenAlex · academic research 41 · Overton · policy documents 23 · from 1 query/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^openalex/)).toBeNull();
    expect(screen.getByText("Free childcare: why, who for and how?")).toBeInTheDocument();
  });

  it("P1 falls back to the scrubbed raw key for an unrecognised backend", () => {
    renderBundle({ backends: [{ backend: "uploaded", count: 5 }] });
    expect(screen.getByText("uploaded 5")).toBeInTheDocument();
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

  it("P4 row edit survives with its group_ids unchanged (title/focus edits must not strip them)", async () => {
    const user = userEvent.setup();
    const { onEditSections } = renderBundle({
      proposal: {
        proposed_sections: [
          {
            title: "What the evidence shows",
            focus: "Answer the question",
            group_ids: ["g-1", "g-2"],
          },
          { title: "Delivery barriers", focus: "Barriers reported" },
        ],
      },
    });
    await user.click(screen.getByRole("button", { name: "Edit section What the evidence shows" }));
    await user.clear(screen.getByLabelText("Section title"));
    await user.type(screen.getByLabelText("Section title"), "What the evidence shows now");
    await user.click(screen.getByRole("button", { name: "Keep edit" }));
    expect(onEditSections).toHaveBeenCalledWith([
      {
        title: "What the evidence shows now",
        focus: "Answer the question",
        group_ids: ["g-1", "g-2"],
      },
      { title: "Delivery barriers", focus: "Barriers reported" },
    ]);
  });

  it("proposedSections carries an opaque group_ids row through, absent when not present", () => {
    expect(
      proposedSections({
        proposal: {
          proposed_sections: [
            { title: "A", focus: "B", group_ids: ["g-1"] },
            { title: "C", focus: "D" },
          ],
        },
      }),
    ).toEqual([
      { title: "A", focus: "B", group_ids: ["g-1"] },
      { title: "C", focus: "D" },
    ]);
  });

  it("proposedSections parses the P4 bundle fail-soft", () => {
    expect(proposedSections({ proposal: { proposed_sections: [{ title: "A", focus: "B" }, { bad: true }] } })).toEqual([
      { title: "A", focus: "B" },
    ]);
    expect(proposedSections(null)).toEqual([]);
  });
});
