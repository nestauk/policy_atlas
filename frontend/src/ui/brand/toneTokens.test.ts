/// <reference types="node" />
// Node types for this file alone, as typeScale.test.ts does: vitest runs with
// CSS processing off, so `?raw` would read the stylesheet as an empty string.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { TONE_HEX, TONE_VAR, toneSquareClass } from "./evidence";

// Paths are relative to the vitest root (`frontend/`).
const cssSource = readFileSync("src/index.css", "utf8");

/** A token's value as `index.css` defines it, lower case. */
function token(name: string): string | undefined {
  return new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`).exec(cssSource)?.[1]?.toLowerCase();
}

describe("the tone squares' colours, defined once", () => {
  it("keeps the export's hex values equal to the palette tokens they name", () => {
    for (const [colour, variable] of Object.entries(TONE_VAR)) {
      const name = /var\(--([a-z0-9-]+)\)/.exec(variable)?.[1] ?? "";
      expect(token(name), colour).toBe(TONE_HEX[colour as keyof typeof TONE_HEX]);
    }
  });

  it("draws the grey square in Line 2", () => {
    expect(toneSquareClass("grey")).toContain("bg-line-2");
    expect(toneSquareClass("grey")).toContain("size-1.5");
  });
});
