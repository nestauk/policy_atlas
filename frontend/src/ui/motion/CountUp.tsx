import { useEffect, useRef, useState } from "react";

/** Duration of one count sweep — long enough to read as movement, short
 *  enough that rapid successive updates never queue visibly. */
const SWEEP_MS = 600;

/**
 * An integer that sweeps toward `value` when it changes. Motion-layer rule
 * (027 strand 10): the sweep only ever marks real data arriving — the
 * component animates on prop change, never on mount. Under
 * `prefers-reduced-motion` it snaps straight to the new value.
 */
export function CountUp({ value, className }: { value: number; className?: string }) {
  const [shown, setShown] = useState(value);
  const fromRef = useRef(value);

  useEffect(() => {
    const from = fromRef.current;
    if (from === value) return;
    fromRef.current = value;
    // Reduced motion: still one frame, but it lands on the final value.
    const sweep = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : SWEEP_MS;
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = sweep === 0 ? 1 : Math.min((t - t0) / sweep, 1);
      setShown(Math.round(from + (value - from) * (1 - (1 - k) ** 3)));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return <span className={className}>{shown}</span>;
}
