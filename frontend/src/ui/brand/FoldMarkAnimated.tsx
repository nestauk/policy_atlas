import { useEffect, useMemo, useState } from "react";

import {
  BLUE,
  BRAND_MARK_SIZE,
  BRAND_MARK_VIEWBOX,
  type FoldPath,
  splashFoldFrames,
  splashPathsAt,
} from "./foldMark";

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Animated fold-mark — loops the fold cycle and applies rotation via SVG
 * transform.
 *
 * @param size - Width and height in CSS pixels.
 * @param foldSpeed - Playback speed multiplier (prototype default 0.4).
 * @param reducedMotion - When true, freeze on the static shut diamond.
 * @param onDark - When true (default) shut-diamond frames render white,
 *   for use on dark (navy) backgrounds. Pass false for light backgrounds
 *   (white/paper nav), which renders them in Nesta blue instead.
 */
export function FoldMarkAnimated({
  size = BRAND_MARK_SIZE,
  foldSpeed = 0.4,
  reducedMotion,
  onDark = true,
}: {
  size?: number;
  foldSpeed?: number;
  reducedMotion?: boolean;
  onDark?: boolean;
}) {
  const shutColour = onDark ? "#ffffff" : BLUE;
  const frames = useMemo(() => splashFoldFrames(undefined, shutColour), [shutColour]);
  const [systemReduced, setSystemReduced] = useState(prefersReducedMotion);
  const reduced = reducedMotion ?? systemReduced;

  // The static shut diamond: the reduced-motion frame, and the first paint
  // before the animation loop's initial tick lands.
  const staticFrame = useMemo(() => {
    const shut = splashPathsAt(0.6, frames, shutColour);
    return { paths: shut.paths, degrees: shut.degrees };
  }, [frames, shutColour]);
  const [liveFrame, setLiveFrame] = useState<{ paths: FoldPath[]; degrees: number }>(staticFrame);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setSystemReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (reduced) return;
    let raf = 0;
    const t0 = performance.now();
    const loop = (now: number) => {
      const clock = ((now - t0) / 1000) * foldSpeed;
      const result = splashPathsAt(clock, frames, shutColour);
      setLiveFrame({ paths: result.paths, degrees: result.degrees });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [foldSpeed, frames, reduced, shutColour]);

  const { paths, degrees } = reduced ? staticFrame : liveFrame;

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox={BRAND_MARK_VIEWBOX}
      className="shrink-0 overflow-visible"
    >
      <g transform={`rotate(${degrees.toFixed(2)})`}>
        {paths.map((p) => (
          <path key={`${p.fill}-${p.d}`} d={p.d} fill={p.fill} />
        ))}
      </g>
    </svg>
  );
}
