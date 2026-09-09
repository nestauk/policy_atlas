import { useEffect } from "react";

/**
 * Seed the task_agent composer from elsewhere on the page.
 *
 * The plan document's "Change this" needs to put a sentence in the composer
 * without touching the plan itself — editing a plan stays conversational, and
 * a control that wrote to the plan directly would bypass the negotiation the
 * task_agent turn exists to record.
 *
 * A DOM `CustomEvent` rather than shared state or a context: the two ends sit
 * in unrelated subtrees, the payload is one string, and nothing needs to
 * persist between dispatches. There is no state here to get out of sync.
 */
const SEED_EVENT = "policy-atlas:seed-composer";

/** Subscribe the composer to seed requests. */
export function useComposerSeed(apply: (text: string) => void): void {
  useEffect(() => {
    const handle = (event: Event) => {
      const text = (event as CustomEvent<string>).detail;
      if (typeof text !== "string") return;
      apply(text);
      document.getElementById("task_agent-message")?.focus();
    };
    window.addEventListener(SEED_EVENT, handle);
    return () => window.removeEventListener(SEED_EVENT, handle);
  }, [apply]);
}

/**
 * Put text in the Task Agent composer from elsewhere on the page (task 044,
 * C18: a scoping plan section's Edit action has no inline editor of its own —
 * the fields are Task Agent-negotiated, so "editing" them is a conversational
 * turn, seeded here rather than built as a second typed-field editor).
 */
export function seedComposer(text: string): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<string>(SEED_EVENT, { detail: text }));
}
