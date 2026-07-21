import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactCompiler from "eslint-plugin-react-compiler";
import globals from "globals";

export default tseslint.config(
  {
    ignores: ["dist", "coverage", "src/api/gen"],
  },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-compiler": reactCompiler,
    },
    rules: {
      // eslint-plugin-react-hooks v7 bundles React Compiler-adjacent lint
      // rules (purity/immutability/set-state-in-render/etc.); the separate
      // eslint-plugin-react-compiler rule below runs the actual compiler's
      // own diagnostics, which is a different (complementary) check.
      ...reactHooks.configs["recommended-latest"].rules,
      ...reactCompiler.configs.recommended.rules,
      // Extended later (task 025 build phase) with the project-wide
      // no-restricted-syntax ban list — kept lean for the F.0 scaffold.
      "no-restricted-syntax": "off",
    },
  },
);
