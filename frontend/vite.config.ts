import { defineConfig } from "vitest/config";
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
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false,
  },
});
