import { useState } from "react";

/**
 * Tells a screen reader, once, that something which was in progress has
 * finished (a reply has arrived).
 *
 * The region stays on the page and is empty until then: a live region that
 * is added with its words already inside is not announced reliably, and one
 * that is removed when the work ends says nothing.
 *
 * Args:
 *   busy: True while the work is in progress.
 *   words: What to say when `busy` turns false.
 */
export function DoneAnnouncer({ busy, words }: { busy: boolean; words: string }) {
  const [wasBusy, setWasBusy] = useState(busy);
  const [said, setSaid] = useState("");
  if (busy !== wasBusy) {
    setWasBusy(busy);
    setSaid(busy ? "" : words);
  }
  return (
    <p role="status" className="sr-only">
      {said}
    </p>
  );
}
