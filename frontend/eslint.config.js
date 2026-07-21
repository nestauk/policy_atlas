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
      // Model-authored and source-derived content is always rendered as text.
      // There is no safe exception for raw HTML in application source.
      "no-restricted-properties": [
        "error",
        {
          property: "dangerouslySetInnerHTML",
          message: "Raw HTML is forbidden in src; render text through scrub() instead.",
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: "Raw HTML is forbidden in src; render text through scrub() instead.",
        },
      ],
    },
  },
);
