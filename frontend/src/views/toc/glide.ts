import { useEffect, useState } from "react";

/*
 * Boxes that glide to their new places while the first draft is drawn
 * (task 054, S12): the canvas lays the sketch out again with each box and
 * connection, and a box that moves eases there instead of jumping. React
 * Flow draws a connection from its boxes' positions, so the positions
 * themselves are eased frame by frame and the lines follow the boxes; a CSS
 * transition on the boxes would leave the lines behind.
 */

/** A place on the canvas, with what makes it the same thing across ids
 *  (a box's layer and words), so the stored box starts where its sketch was. */
export interface GlideTarget {
  x: number;
  y: number;
  key: string;
}

type Point = { x: number; y: number };

/** DESIGN.md § Motion: 300 ms, a value landing or a height easing. */
export const GLIDE_MS = 300;

/** The strong ease-out, `--ease-out-strong`: cubic-bezier(0.23, 1, 0.32, 1). */
const [X1, Y1, X2, Y2] = [0.23, 1, 0.32, 1];

const bezier = (t: number, a: number, b: number) => 3 * a * t * (1 - t) ** 2 + 3 * b * t ** 2 * (1 - t) + t ** 3;

/**
 * The strong ease-out at a point in time.
 *
 * Args:
 *   x: How far through the glide, 0 to 1.
 *
 * Returns:
 *   How far along the way, 0 to 1.
 */
export function easeOutStrong(x: number): number {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  // The curve's time for this x, by bisection: monotone, so it always converges.
  let low = 0;
  let high = 1;
  for (let i = 0; i < 24; i += 1) {
    const mid = (low + high) / 2;
    if (bezier(mid, X1, X2) < x) low = mid;
    else high = mid;
  }
  return bezier((low + high) / 2, Y1, Y2);
}

interface Glide {
  /** The targets this glide goes to, as one string. */
  signature: string;
  from: ReadonlyMap<string, Point>;
  to: ReadonlyMap<string, GlideTarget>;
  /** When it began (a frame time); null until its first frame; 0 when there is nothing to ease. */
  start: number | null;
  /** Whether it eased: the glide after the last eased one still eases (the swap to the stored graph). */
  eased: boolean;
}

const signatureOf = (targets: ReadonlyMap<string, GlideTarget>) => [...targets].map(([id, at]) => `${id}:${at.x},${at.y}`).join("|");

/**
 * Each item's place on screen while `active`: a moved item eases from where
 * it was shown to its new place over GLIDE_MS on the strong ease-out; a new
 * item starts where a shown item with the same `key` was (the sketch's box,
 * when the stored graph replaces it) or at its place. The first change after
 * `active` ends still eases, so the swap glides too. Otherwise, and under
 * reduced motion, items are at their places at once.
 *
 * Args:
 *   targets: Each item's place, by id.
 *   active: True while the sketch is drawn.
 *   reduced: The reader asks for less motion.
 *
 * Returns:
 *   Each item's place to draw now, by id.
 */
export function useGlide(targets: ReadonlyMap<string, GlideTarget>, active: boolean, reduced: boolean): ReadonlyMap<string, Point> {
  const signature = signatureOf(targets);
  const [glide, setGlide] = useState<Glide>(() => ({ signature, from: targets, to: targets, start: 0, eased: active }));
  const [now, setNow] = useState(0);
  const progress = glide.start === null ? 0 : glide.start === 0 ? 1 : Math.min(1, (now - glide.start) / GLIDE_MS);
  const eased = easeOutStrong(progress);
  const shown = (id: string): Point | undefined => {
    const to = glide.to.get(id);
    if (to === undefined) return undefined;
    const from = glide.from.get(id) ?? to;
    return { x: from.x + (to.x - from.x) * eased, y: from.y + (to.y - from.y) * eased };
  };
  const running = glide.start === null || (glide.start !== 0 && progress < 1);

  let current = glide;
  if (glide.signature !== signature) {
    const ease = (active || glide.eased) && !reduced && typeof window !== "undefined" && typeof window.requestAnimationFrame === "function";
    // A new item takes the place of a shown one with the same key.
    const byKey = new Map<string, Point>();
    for (const [id, at] of glide.to) {
      const point = shown(id);
      if (point !== undefined && !byKey.has(at.key)) byKey.set(at.key, point);
    }
    const from = new Map<string, Point>();
    for (const [id, at] of targets) from.set(id, shown(id) ?? byKey.get(at.key) ?? at);
    current = { signature, from: ease ? from : targets, to: targets, start: ease ? null : 0, eased: ease && active };
    setGlide(current);
  }

  useEffect(() => {
    if (!running) return undefined;
    const frame = window.requestAnimationFrame((time) => {
      setGlide((last) => (last.start === null ? { ...last, start: time } : last));
      setNow(time);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [running, glide, now]);

  if (current !== glide) {
    // This render already shows the new glide's start.
    return new Map([...targets].map(([id, at]) => [id, current.from.get(id) ?? at]));
  }
  return new Map([...targets].map(([id, at]) => [id, shown(id) ?? at]));
}
