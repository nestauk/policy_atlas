import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { scrub, Scrubbed } from "./scrub";

describe("scrub", () => {
  it("normalizes composed display text to NFC", () => {
    expect(scrub("Cafe\u0301")).toBe("Café");
  });

  it("removes a bidi override injection", () => {
    expect(scrub("policy\u202Efdp")).toBe("policyfdp");
  });

  it("removes zero-width smuggling", () => {
    expect(scrub("screen\u200Bed in")).toBe("screened in");
  });

  it("removes a NUL byte and ANSI escape sequence", () => {
    expect(scrub("safe\u0000 text\u001B[31m red")).toBe("safe text[31m red");
  });

  it("removes a mixed control, bidi, and invisible attack while keeping tabs and newlines", () => {
    expect(scrub("A\u2066B\uFEFFC\u009BD\nE\tF\u0007")).toBe("ABCD\nE\tF");
  });
});

describe("Scrubbed", () => {
  it("renders scrubbed text through a chosen element", () => {
    render(<Scrubbed as="p" value={"A\u202EB"} />);
    expect(screen.getByText("AB").tagName).toBe("P");
  });
});
