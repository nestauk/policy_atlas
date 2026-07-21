import { configDefaults, defineConfig } from "vitest/config";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
//
// @vitejs/plugin-react 6.x (Vite 8 / Rolldown era) dropped the classic
// `react({ babel: { plugins: [...] } })` option — the plugin no longer runs
// Babel itself. React Compiler wiring now goes through a separate
// `@rolldown/plugin-babel` babel() plugin combined with the
// `reactCompilerPreset` helper exported from @vitejs/plugin-react. See
// node_modules/@vitejs/plugin-react/README.md "React Compiler" section.
export default defineConfig({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] }), tailwindcss()],
  server: {
    // Proxy API + SSE calls to the local backend dev server (`make -C backend
    // dev`, port 8000) so `VITE_API_BASE_URL`'s default of `/api` resolves in
    // dev without CORS — mock mode (VITE_MOCK=1) never reaches this, since
    // `installMockApi()` intercepts fetch before any request leaves the page.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false,
    // `e2e/` holds Playwright specs (`pnpm e2e`), not vitest ones — vitest's
    // default include glob would otherwise pick up `e2e/journey.spec.ts` too
    // and fail on `test.describe` outside a Playwright runner.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
