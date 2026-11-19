import { renameSync } from "node:fs";
import { resolve } from "node:path";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

import base from "./vite.config.ts";

/*
 * The ops pages' build (task 065, plan P1 and P3): the same project, plugins
 * and theme as the public app, with only the page and the output folder
 * changed. `pnpm build:ops` writes into `backend/ops-ui/` (gitignored), which
 * the ops service serves; the public `pnpm build` and `dist/` never see it.
 */

const OUT_DIR = "../backend/ops-ui";

/**
 * The page is `ops.html` here, but the ops service answers every path with
 * `index.html`, so the build renames it. In `vite` dev and `vite preview`
 * with this config, a page request is answered with `ops.html` too, so the
 * browser router's deep links work locally.
 */
const opsPage: Plugin = {
  name: "policy-atlas-ops-page",
  configureServer(server) {
    server.middlewares.use((request, _response, next) => {
      if (request.headers.accept?.includes("text/html")) request.url = "/ops.html";
      next();
    });
  },
  writeBundle(options) {
    if (options.dir) renameSync(resolve(options.dir, "ops.html"), resolve(options.dir, "index.html"));
  },
};

export default defineConfig({
  ...base,
  plugins: [...(base.plugins ?? []), opsPage],
  build: {
    ...base.build,
    outDir: OUT_DIR,
    emptyOutDir: true,
    rollupOptions: { input: "ops.html" },
  },
});
