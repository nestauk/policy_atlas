import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

/*
 * The public app gains no ops code (contract B6, plan P3): nothing outside
 * `src/ops/` imports from it, and the public build's page is not the ops page.
 */

const SRC = resolve(__dirname, "..");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return path === __dirname ? [] : sources(path);
    return /\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

describe("the ops bundle stays separate", () => {
  it("no file outside src/ops imports from it", () => {
    const offenders = sources(SRC).filter((path) => /from\s+["'][^"']*\/ops(\/|["'])/.test(readFileSync(path, "utf8")));
    expect(offenders.map((path) => relative(SRC, path))).toEqual([]);
  });

  it("the public build's input is not the ops page", () => {
    const config = readFileSync(resolve(SRC, "..", "vite.config.ts"), "utf8");
    expect(config).not.toContain("ops.html");
  });
});
