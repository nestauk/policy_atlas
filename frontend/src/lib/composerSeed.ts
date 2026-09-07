import { useEffect } from "react";

/**
 * Seed the planning composer from elsewhere on the page.
 *
 * The plan document's "Change this" needs to put a sentence in the composer
 * without touching the plan itself — editing a plan stays conversational, and
 * a control that wrote to the plan directly would bypass the negotiation the
 * planning turn exists to record.
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
      document.getElementById("planning-message")?.focus();
    };
    window.addEventListener(SEED_EVENT, handle);
    return () => window.removeEventListener(SEED_EVENT, handle);
  }, [apply]);
}
