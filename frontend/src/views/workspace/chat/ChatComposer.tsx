import { useState } from "react";

import { useComposerDraft } from "../../../store";
import { Button } from "../../../ui/brand/Button";
import { Composer } from "../PlanningPane";

/** Chat wrapper around the shared planning composer and its session draft.
 *
 * Args:
 *   props: Conversation controls and stream status.
 *
 * Returns:
 *   The shared composer or the in-flight stop control.
 */
export function ChatComposer({ conversationId, isStreaming, disabledReason, onSend, onStop }: { conversationId: string; isStreaming: boolean; disabledReason?: string | null; onSend: (message: string) => void; onStop: () => void }) {
  const [draft, setDraft] = useComposerDraft(conversationId);
  const [submitting, setSubmitting] = useState(false);
  const send = () => { const message = draft.trim(); if (!message || submitting || isStreaming || disabledReason) return; setSubmitting(true); setDraft(""); Promise.resolve(onSend(message)).finally(() => setSubmitting(false)); };
  if (isStreaming) return <div><div className="flex items-center justify-between border border-line bg-ground px-3 py-2 text-caption text-grey"><span>Checking the evidence…</span><Button size="sm" variant="secondary" onClick={onStop}>Stop</Button></div></div>;
  return <div>{disabledReason && <p className="mb-2 text-caption text-grey">{disabledReason}</p>}<Composer value={draft} onChange={setDraft} onSubmit={send} placeholder="Ask about the evidence" disabled={Boolean(disabledReason)} sendDisabled={submitting || Boolean(disabledReason)} /></div>;
}
