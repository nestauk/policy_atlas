import { useEffect, useRef, useState } from "react";

import { useComposerDraft } from "../../../store";
import { Button } from "../../../ui/brand/Button";
import { Composer } from "../TaskAgentPane";

/** Chat wrapper around the shared task_agent composer and its session draft.
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
  // The field is replaced by the Stop control while a reply streams, which
  // drops focus to the page. When the field comes back, focus returns to it,
  // unless the reader has put focus somewhere else in the meantime.
  const wasStreaming = useRef(isStreaming);
  useEffect(() => {
    const ended = wasStreaming.current && !isStreaming;
    wasStreaming.current = isStreaming;
    if (ended && document.activeElement === document.body) document.getElementById(`chat-message-${conversationId}`)?.focus();
  }, [isStreaming, conversationId]);
  const send = () => { const message = draft.trim(); if (!message || submitting || isStreaming || disabledReason) return; setSubmitting(true); setDraft(""); Promise.resolve(onSend(message)).finally(() => setSubmitting(false)); };
  if (isStreaming) return <div><div className="flex items-center justify-between border border-line bg-ground px-3 py-2 text-body text-grey"><span>Checking the evidence…</span><Button size="sm" variant="secondary" onClick={onStop}>Stop</Button></div></div>;
  return <div>{disabledReason && <p className="mb-2 text-body text-grey">{disabledReason}</p>}<Composer id={`chat-message-${conversationId}`} label="Message the Agent" value={draft} onChange={setDraft} onSubmit={send} placeholder="Ask about the evidence" disabled={Boolean(disabledReason)} sendDisabled={submitting || Boolean(disabledReason)} /></div>;
}
