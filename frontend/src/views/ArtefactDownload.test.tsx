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
    render(<ArtefactDownload artefact={mockArtefact} />);
    await user.click(screen.getByRole("button", { name: "Download" }));
    await user.click(screen.getByRole("menuitem", { name: "Markdown" }));
    expect(download).toHaveBeenCalledWith(
      "policy-options-for-healthier-childhoods.md",
      expect.stringContaining("## References"),
      "text/markdown",
    );
    expect(download.mock.calls[0][1]).toContain("[1]");
  });
});
