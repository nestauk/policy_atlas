import { useState } from "react";
import type { FormEvent } from "react";

import { Button } from "../ui/brand/Button";

/** sessionStorage key for a pasted dev token. Never `localStorage` — the
 *  token must not survive a browser restart or get picked up by anything
 *  scanning committed/persisted storage. */
export const DEV_TOKEN_STORAGE_KEY = "policy_atlas.dev_token";

/**
 * Visibly non-production "paste a dev token" surface. Used embedded on the
 * splash Sign-in panel, or full-viewport when a host wants the old gate.
 */
export function DevTokenLoginPanel({
  onSubmit,
  embedded = false,
}: {
  onSubmit: (token: string) => void;
  /** When true, omit the full-viewport chrome (splash Sign-in panel). */
  embedded?: boolean;
}) {
  const [draft, setDraft] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = draft.trim();
    if (trimmed) onSubmit(trimmed);
  }

  const form = (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-md border border-line-2 bg-paper p-6 shadow-[0_1px_3px_rgba(15,41,74,0.05),0_8px_24px_rgba(15,41,74,0.04)]"
    >
      <p className="mb-3 inline-block border border-[#f3d99a] bg-yellow-tint px-2.5 py-1 text-caption font-semibold text-[#8a5a00]">
        Dev-only sign-in — never used in production
      </p>
      <h1 className="mb-2 font-display text-heading font-semibold text-navy">Paste a dev token</h1>
      <p className="mb-4 text-meta text-grey">
        Mint one with the backend dev-issuer CLI. Stored in this tab&apos;s session storage only —
        cleared on sign-out or when the tab closes.
      </p>
      <label htmlFor="dev-token" className="sr-only">
        Dev token
      </label>
      <textarea
        id="dev-token"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        rows={4}
        spellCheck={false}
        autoComplete="off"
        placeholder="eyJhbGciOi..."
        className="mb-4 w-full resize-none border border-line-2 bg-paper-2 p-2.5 font-mono text-caption text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
      />
      <Button type="submit" disabled={draft.trim().length === 0}>
        Sign in
      </Button>
    </form>
  );

  if (embedded) return form;
  return <main className="flex min-h-svh items-center justify-center bg-ground p-6">{form}</main>;
}
