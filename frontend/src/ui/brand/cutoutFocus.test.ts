/// <reference types="node" />
// Node types for this file alone, as in typeScale.test.ts.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * A cut-corner element must draw its focus ring inside its box.
 *
 * The `cutout` utilities use `clip-path`, which clips everything outside the
 * polygon, and that includes the house focus ring (an outline 2px outside the
 * box). A cut-corner element with no inset ring of its own has no visible
 * focus at all (WCAG 2.4.7), and nothing else catches it: the ring is clipped
 * in the browser, not in the DOM.
 *
 * A source-text assertion, because the failure is a class that is absent.
 */
const INSET_RING = /focus-visible:-outline-offset-|CUT_FOCUS_RING/;

/** Lines that put a cutout class on a `Button`, whose cut variants carry the ring. */
const ON_A_BUTTON = [
  '{ variant: "primary", size: "sm", class: "cutout-sm" }',
  '{ variant: "start", size: "sm", class: "cutout-sm" }',
  'className="cutout-2 h-10 w-12 justify-center p-0"',
];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

describe("cut-corner focus rings", () => {
  it("every element with a cutout class has an inset focus ring", () => {
    const uses = sourceFiles("src").flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .filter((line) => /["'`\s]cutout(-2|-sm)?[\s"'`]/.test(line) && !/^\s*(\*|\/\/|\/\*)/.test(line))
        .map((line) => ({ file, line: line.trim() })),
    );
    // The scan finds the uses it is meant to guard.
    expect(uses.length).toBeGreaterThanOrEqual(3);
    const withoutRing = uses.filter(
      ({ line }) => !INSET_RING.test(line) && !ON_A_BUTTON.some((allowed) => line.includes(allowed)),
    );
    expect(withoutRing).toEqual([]);
  });
});
