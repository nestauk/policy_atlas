import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactCompiler from "eslint-plugin-react-compiler";
import jsxA11y from "eslint-plugin-jsx-a11y";
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
      "jsx-a11y": jsxA11y,
    },
    rules: {
      // eslint-plugin-react-hooks v7 bundles React Compiler-adjacent lint
      // rules (purity/immutability/set-state-in-render/etc.); the separate
      // eslint-plugin-react-compiler rule below runs the actual compiler's
      // own diagnostics, which is a different (complementary) check.
      ...reactHooks.configs["recommended-latest"].rules,
      ...reactCompiler.configs.recommended.rules,
      // Accessibility rules that can be read off the JSX (WCAG 2.2 AA is the
      // target). They catch a minority of problems: a missing name, a click
      // handler with no key handler, a wrong role. Keyboard order, screen
      // reader output, contrast and zoom still need the manual checks in
      // docs/tasks/067-accessibility.
      ...jsxA11y.flatConfigs.recommended.rules,
      // Explicit roles the rule calls redundant are deliberate here. A list
      // with `list-style: none` loses its list role in Safari with
      // VoiceOver, and a table whose rows are restacked with CSS `display`
      // loses its table roles, unless the role is written out.
      "jsx-a11y/no-redundant-roles": [
        "error",
        { ul: ["list"], ol: ["list"], tbody: ["rowgroup"], thead: ["rowgroup"] },
      ],
      "jsx-a11y/no-interactive-element-to-noninteractive-role": [
        "error",
        { tr: ["none", "presentation"], canvas: ["img"], td: ["cell"] },
      ],
      // `autoFocus` is used only on a field that appears because the user
      // asked for it (a rename, an inline edit, the New task question): the
      // field is where their next key press belongs. The rule targets focus
      // that moves on page load without being asked.
      "jsx-a11y/no-autofocus": "off",
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
