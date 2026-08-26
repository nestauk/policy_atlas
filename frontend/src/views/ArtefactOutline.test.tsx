import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ContentsSidebar, SectionDisclosure, sectionSummary } from "./ArtefactOutline";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { AnnotatedProse } from "./ArtefactView";

describe("sectionSummary", () => {
  const blocks = [{ prose: "Universal provision raised uptake. More detail follows here." }];

  it("uses the verified block summary when one exists", () => {
    expect(
      sectionSummary({ title: "T", role: "standard", summary: "The takeaway.", summary_status: "verified", blocks }),
    ).toEqual({ text: "The takeaway." });
  });

  it("falls back to the section's own first sentence for failed or absent summaries", () => {
    for (const summary_status of ["failed", null] as const) {
      expect(
        sectionSummary({ title: "T", role: "standard", summary: null, summary_status, blocks }),
      ).toEqual({ text: "Universal provision raised uptake." });
    }
  });

  it("never uses an unverified summary text as a summary", () => {
    expect(
      sectionSummary({ title: "T", role: "standard", summary: "pending text", summary_status: "pending", blocks }),
    ).toEqual({ text: "Universal provision raised uptake." });
  });
});

describe("SectionDisclosure", () => {
  const section = {
    title: "What the evidence shows",
    role: "standard" as const,
    summary: "The takeaway.",
    summary_status: "verified" as const,
    blocks: [{ prose: "Full cited prose." }],
  };

  it("collapsed by default: title + summary visible, prose hidden, real button", async () => {
    const user = userEvent.setup();
    render(
      <SectionDisclosure id="s1" section={section} collapsible defaultOpen={false}>
        <p>Full cited prose.</p>
      </SectionDisclosure>,
    );
    const toggle = screen.getByRole("button", { expanded: false });
    expect(screen.getByText("The takeaway.")).toBeInTheDocument();
    expect(screen.queryByText("Full cited prose.")).toBeNull();
    await user.click(toggle);
    expect(screen.getByRole("button", { expanded: true })).toBeInTheDocument();
    expect(screen.getByText("Full cited prose.")).toBeInTheDocument();
  });

  it("fallback summaries render unmarked — provenance is not user copy", () => {
    render(
      <SectionDisclosure
        id="s2"
        section={{ ...section, summary: null, summary_status: "failed" }}
        collapsible
        defaultOpen={false}
      >
        <p>Prose.</p>
      </SectionDisclosure>,
    );
    // The first-sentence fallback still shows; the dev-facing marker doesn't.
    expect(screen.queryByText(/no checked summary/)).toBeNull();
  });

  it("non-collapsible sections render in full with no toggle", () => {
    render(
      <SectionDisclosure id="s3" section={{ ...section, role: "key_findings" }} collapsible={false} defaultOpen>
        <p>Full cited prose.</p>
      </SectionDisclosure>,
    );
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Full cited prose.")).toBeInTheDocument();
  });

  it("expands collapsed prose when the browser is about to print", () => {
    render(
      <SectionDisclosure id="s-print" section={section} collapsible defaultOpen={false}>
        <p>Full cited prose.</p>
      </SectionDisclosure>,
    );
    expect(screen.queryByText("Full cited prose.")).toBeNull();
    act(() => {
      window.dispatchEvent(new Event("beforeprint"));
    });
    expect(screen.getByText("Full cited prose.")).toBeInTheDocument();
  });

  it("a claim span inside the section survives collapse then re-expand", async () => {
    const user = userEvent.setup();
    const prose = "Universal provision raised uptake in the review.";
    const text = "raised uptake";
    const start = prose.indexOf(text);
    const block = {
      block_id: "b3",
      prose,
      claims: [
        {
          claim_id: "c3",
          claim_type: "citation" as const,
          text,
          span: [start, start + text.length] as [number, number],
          citations: [],
        },
      ],
    };
    render(
      <TooltipProvider>
        <SectionDisclosure id="s4" section={section} collapsible defaultOpen>
          <AnnotatedProse block={block} onOpenClaim={vi.fn()} />
        </SectionDisclosure>
      </TooltipProvider>,
    );
    expect(screen.getByRole("button", { name: /raised uptake/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { expanded: true }));
    expect(screen.queryByRole("button", { name: /raised uptake/ })).toBeNull();

    await user.click(screen.getByRole("button", { expanded: false }));
    expect(screen.getByRole("button", { name: /raised uptake/ })).toBeInTheDocument();
  });

  it("expands a collapsed section when its contents link is clicked", async () => {
    const user = userEvent.setup();
    const scrollIntoView = vi.fn();
    const scrollTo = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollIntoView;
    HTMLElement.prototype.scrollTo = scrollTo;
    render(
      <>
        <ContentsSidebar entries={[{ id: "s1", title: section.title }]} />
        <SectionDisclosure id="s1" section={section} collapsible defaultOpen={false}>
          <p>Full cited prose.</p>
        </SectionDisclosure>
      </>,
    );
    expect(screen.queryByText("Full cited prose.")).toBeNull();
    await user.click(screen.getByRole("link", { name: section.title }));
    expect(screen.getByText("Full cited prose.")).toBeInTheDocument();
    expect(screen.getByRole("button", { expanded: true })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: section.title })).toHaveAttribute(
      "aria-current",
      "location",
    );
    expect(scrollIntoView.mock.calls.length + scrollTo.mock.calls.length).toBeGreaterThan(0);
    history.replaceState(null, "", window.location.pathname);
  });

  it("scrolls to a section that is already expanded", async () => {
    const user = userEvent.setup();
    const scrollIntoView = vi.fn();
    const scrollTo = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollIntoView;
    HTMLElement.prototype.scrollTo = scrollTo;
    render(
      <>
        <ContentsSidebar entries={[{ id: "s1", title: section.title }]} />
        <SectionDisclosure id="s1" section={section} collapsible defaultOpen>
          <p>Full cited prose.</p>
        </SectionDisclosure>
      </>,
    );
    await user.click(screen.getByRole("link", { name: section.title }));
    expect(scrollIntoView.mock.calls.length + scrollTo.mock.calls.length).toBeGreaterThan(0);
    history.replaceState(null, "", window.location.pathname);
  });
});

describe("AnnotatedProse bullets (fork B)", () => {
  it("renders bullet prose as list items with spans anchored inside bullets", () => {
    const prose = "- Uptake rose under universal provision.\n- Travel safety shaped attendance.";
    const block = {
      block_id: "b1",
      prose,
      claims: [
        {
          claim_id: "c1",
          claim_type: "citation" as const,
          text: "universal provision",
          span: [20, 39] as [number, number],
          citations: [],
        },
      ],
    };
    render(<TooltipProvider><AnnotatedProse block={block} onOpenClaim={vi.fn()} /></TooltipProvider>);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /universal provision/ })).toBeInTheDocument();
  });

  it("a span crossing a bullet boundary degrades to the anchored list, never mis-renders", () => {
    const prose = "- First bullet end\n- second bullet start.";
    const crossingText = "end\n- second";
    const start = prose.indexOf("end");
    const block = {
      block_id: "b2",
      prose,
      claims: [
        {
          claim_id: "c2",
          claim_type: "citation" as const,
          text: crossingText,
          span: [start, start + crossingText.length] as [number, number],
          citations: [],
        },
      ],
    };
    render(<TooltipProvider><AnnotatedProse block={block} onOpenClaim={vi.fn()} /></TooltipProvider>);
    // Both bullets render as plain text; the claim survives as one anchored
    // entry below the list rather than a span split across two bullets.
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const anchored = screen.getByRole("button");
    expect(anchored.textContent ?? "").toContain("second");
  });

  it("bolds the lead before the first colon-space and leaves no-colon bullets unbolded", () => {
    const prose =
      "- Universal breakfast helped: eleven of fifteen evaluations reported higher uptake.\n- No colon on this line.";
    render(
      <TooltipProvider>
        <AnnotatedProse
          block={{ block_id: "b-lead", prose, claims: [] }}
          onOpenClaim={vi.fn()}
        />
      </TooltipProvider>,
    );
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0].querySelector("strong")?.textContent).toBe("Universal breakfast helped:");
    expect(items[0].textContent).toContain("eleven of fifteen");
    expect(items[1].querySelector("strong")).toBeNull();
    expect(items[1].textContent).toContain("No colon on this line.");
  });

  it("marks a gap bullet distinctly from an evidence bullet", () => {
    const prose = "- No rural trials: the coverage record is empty.";
    const text = "No rural trials: the coverage record is empty.";
    render(
      <TooltipProvider>
        <AnnotatedProse
          block={{
            block_id: "b-gap",
            prose,
            claims: [
              {
                claim_id: "g1",
                claim_type: "gap" as const,
                text,
                span: [2, 2 + text.length] as [number, number],
                citations: [],
              },
            ],
          }}
          onOpenClaim={vi.fn()}
        />
      </TooltipProvider>,
    );
    const marker = screen.getByRole("listitem").querySelector("[aria-hidden]");
    expect(marker?.className).toContain("bg-yellow");
  });
});
