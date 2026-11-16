import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { TocCodeText } from "./codeLinks";

describe("TocCodeText", () => {
  it("links the theory's own codes and the Result tab, nothing else", () => {
    render(
      <MemoryRouter>
        <p>
          <TocCodeText taskId="t1" codes={new Set(["#1", "#15", "S3"])} text="Check #15 and S3, not #150 or S30. Read the Result tab." />
        </p>
      </MemoryRouter>,
    );
    expect(screen.getAllByRole("link").map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["#15", "/tasks/t1/result?focus=%2315"],
      ["S3", "/tasks/t1/result?focus=S3"],
      ["Result tab", "/tasks/t1/result"],
    ]);
  });
});
