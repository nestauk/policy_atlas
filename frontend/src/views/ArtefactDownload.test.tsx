import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockArtefact } from "../mock/fixtures";
import { ArtefactDownload } from "./ArtefactDownload";
import * as presentation from "./artefactPresentation";

describe("ArtefactDownload", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("prints when PDF is chosen", async () => {
    const user = userEvent.setup();
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    render(<ArtefactDownload artefact={mockArtefact} />);
    await user.click(screen.getByRole("button", { name: "Download" }));
    await user.click(screen.getByRole("menuitem", { name: "PDF" }));
    await waitFor(() => expect(print).toHaveBeenCalledOnce());
  });

  it("downloads markdown when Markdown is chosen", async () => {
    const user = userEvent.setup();
    const download = vi.spyOn(presentation, "triggerTextDownload").mockImplementation(() => undefined);
    render(<ArtefactDownload artefact={mockArtefact} question="Which approaches work?" />);
    await user.click(screen.getByRole("button", { name: "Download" }));
    await user.click(screen.getByRole("menuitem", { name: "Markdown" }));
    // The generated title names the file; the question heads it, as on the
    // page (round 10, D1).
    expect(download).toHaveBeenCalledWith(
      "policy-options-for-healthier-childhoods.md",
      expect.stringContaining("## References"),
      "text/markdown",
    );
    const markdown = download.mock.calls[0][1];
    expect(markdown.startsWith("# Which approaches work?\n")).toBe(true);
    expect(markdown).toContain("[1]");
    expect(markdown).toContain("1. Sampleton A, Mockford C (2022). Universal breakfast clubs and diet quality. BMJ Open.");
    expect(markdown.indexOf("### Most relevant sources")).toBeLessThan(markdown.indexOf("### References"));
  });
});
