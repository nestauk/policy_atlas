/// <reference types="node" />
// Node types are referenced for this file alone: tsconfig.app.json restricts
// `types` to vite/client because the app is browser code, and widening it for
// one test would be the wrong trade. `?raw` is not an option for the CSS —
// vitest runs with CSS processing off, so it resolves to an empty string.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

// Paths are relative to the vitest root (`frontend/`).
const cssSource = readFileSync("src/index.css", "utf8");
const cnSource = readFileSync("src/ui/brand/cn.ts", "utf8");

/**
 * The type scale must exist in both places or not at all.
 *
 * In task 028 a scale token was added to `index.css` and not registered with
 * tailwind-merge. An unregistered `text-<x>` is classified as a text COLOUR,
 * so `cn("text-white", "text-meta")` silently dropped `text-white` and every
 * primary button shipped ink-on-blue. Typecheck, lint, 185 tests and the mock
 * e2e were all green — nothing mechanical caught it.
 *
 * This test is that missing gate. It is deliberately a source-text assertion
 * rather than an import, because the failure lives in the *text* of two files
 * that have no reason to import each other.
 */
function tokensInCss(): string[] {
  const theme = cssSource.slice(cssSource.indexOf("@theme"));
  // `--text-body: 16px` yes; `--text-body--line-height: 1.55` no.
  return [...theme.matchAll(/--text-([a-z0-9]+):/g)].map((match) => match[1]);
}

function tokensInTailwindMerge(): string[] {
  const group = /"font-size":\s*\[\s*\{\s*text:\s*\[([^\]]*)\]/s.exec(cnSource);
  if (group === null) throw new Error("could not find the font-size class group in cn.ts");
  return [...group[1].matchAll(/"([a-z0-9]+)"/g)].map((match) => match[1]);
}

describe("type scale registration", () => {
  it("registers every index.css --text-* token with tailwind-merge", () => {
    expect([...tokensInTailwindMerge()].sort()).toEqual([...tokensInCss()].sort());
  });

  it("finds a non-trivial scale, so a broken regex cannot pass vacuously", () => {
    const tokens = tokensInCss();
    expect(tokens.length).toBeGreaterThanOrEqual(6);
    expect(tokens).toContain("body");
    expect(tokens).toContain("display");
  });
});
