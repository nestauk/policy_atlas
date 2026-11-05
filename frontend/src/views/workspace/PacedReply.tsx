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
  const started = revealedSoFar.get(turnId);
  // The history shows at once; a streamed reply starts from nothing, and a
  // stored one carries on from its streamed turn.
  const initial = streamed ? (started ?? 0) : started;
  const revealed = useRevealedText(text, !streamed && started === undefined, initial);
  const chars = Array.from(revealed.text);
  const shown = chars.length;
  useEffect(() => {
    if (streamed || revealedSoFar.has(turnId)) remember(turnId, shown);
  }, [turnId, shown, streamed]);

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
