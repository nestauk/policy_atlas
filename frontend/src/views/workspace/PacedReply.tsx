import { Fragment, useEffect } from "react";

import { scrub } from "../../lib/scrub";
import { useRevealedText } from "../streamPacing";

/** How far each reply's reveal has got, by client turn id, so the stored
 *  turn that replaces a streamed one carries on from where it was. */
const revealedSoFar = new Map<string, number>();

/** Replies kept in the map; the oldest go first. */
const KEPT = 20;

function remember(id: string, shown: number): void {
  revealedSoFar.delete(id);
  revealedSoFar.set(id, shown);
  while (revealedSoFar.size > KEPT) {
    const oldest = revealedSoFar.keys().next().value;
    if (oldest === undefined) break;
    revealedSoFar.delete(oldest);
  }
}

/**
 * A reply's text at a steady pace, shared by the Task Agent and the chats
 * (owner, round 14: the chats stream the same way): whole words at a steady
 * rate catching up within 800 ms (`useRevealedText`). The history shows at
 * once; a streamed reply starts from nothing, and the stored turn that
 * replaces it carries on from where it was (keyed by the client turn id).
 *
 * Args:
 *   turnId: The turn's client id, shared by the streamed and stored turn.
 *   text: The reply so far.
 *   streamed: True for the streamed turn; false for the stored one.
 *
 * Returns:
 *   The revealed text and the offsets where recent batches began.
 */
export function usePacedText(
  turnId: string,
  text: string,
  streamed: boolean,
): { text: string; batches: readonly number[] } {
  const started = revealedSoFar.get(turnId);
  const initial = streamed ? (started ?? 0) : started;
  const revealed = useRevealedText(text, !streamed && started === undefined, initial);
  const shown = Array.from(revealed.text).length;
  useEffect(() => {
    if (streamed || revealedSoFar.has(turnId)) remember(turnId, shown);
  }, [turnId, shown, streamed]);
  return revealed;
}

/**
 * The Task Agent's reply at a steady pace (task 058, round 9; the animation
 * sweep's entry 6): the planner's deltas land in bursts, so the reply is
 * revealed the way the Result tab reveals the report (`useRevealedText`:
 * whole words at a steady rate, catching up within 800 ms), and the words
 * each frame reveals fade in over 150 ms, opacity only. A stored reply
 * that was never streamed here (the history) shows at once; one that
 * replaces the streamed turn it came from carries on from the same place.
 * Under reduced motion the words appear without the fade; the pacing stays.
 *
 * Args:
 *   turnId: The turn's client id, shared by the streamed and stored turn.
 *   text: The reply so far.
 *   streamed: True for the streamed turn; false for the stored one.
 */
export function PacedReply({ turnId, text, streamed }: { turnId: string; text: string; streamed: boolean }) {
  const revealed = usePacedText(turnId, text, streamed);
  const chars = Array.from(revealed.text);
  const shown = chars.length;

  const cuts = revealed.batches.filter((cut) => cut > 0 && cut < shown);
  if (cuts.length === 0) return <>{scrub(revealed.text)}</>;
  const bounds = [0, ...cuts, shown];
  return (
    <>
      {bounds.slice(0, -1).map((from, at) => {
        const piece = scrub(chars.slice(from, bounds[at + 1]).join(""));
        return at === 0 ? (
          <Fragment key={from}>{piece}</Fragment>
        ) : (
          <span key={from} className="anim-word-in">
            {piece}
          </span>
        );
      })}
    </>
  );
}
