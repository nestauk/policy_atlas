import { useEffect, useRef, useState } from "react";

import {
  PASTEL_SHEET_COLOURS,
  SPLASH_LAYOUT,
  splashFoldFrames,
  splashPathsAt,
  type FoldPath,
} from "../../ui/brand/foldMark";

interface PlacedSheet {
  x: string;
  y: string;
  sizePx: number;
  opacity: number;
  off: number;
  layoutIndex: number;
  paths: FoldPath[];
  degrees: number;
}

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Full-bleed animated fold-mark constellation behind the splash hero copy.
 *
 * Placement clears overlapping seeds and the live copy box, matching the
 * design prototype. Freezes under `prefers-reduced-motion`.
 */
export function SplashField({
  foldSpeed = 0.4,
  spread = 1,
  sheetScale = 1,
  minGap = 12,
}: {
  foldSpeed?: number;
  spread?: number;
  sheetScale?: number;
  minGap?: number;
}) {
  const fieldRef = useRef<HTMLDivElement>(null);
  const copyRef = useRef<HTMLElement | null>(null);
  const frames = useRef(splashFoldFrames()).current;
  const [sheets, setSheets] = useState<PlacedSheet[]>([]);
  const [reduced, setReduced] = useState(prefersReducedMotion);
  const copyBox = useRef<{ left: number; right: number; top: number; bottom: number } | null>(
    null,
  );
  const fieldBox = useRef<{ w: number; h: number } | null>(null);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const measure = () => {
    const field = fieldRef.current;
    copyRef.current = document.getElementById("splash-copy");
    if (!field) return false;
    const o = field.getBoundingClientRect();
    let moved = false;
    if (!fieldBox.current || fieldBox.current.w !== o.width || fieldBox.current.h !== o.height) {
      fieldBox.current = { w: o.width, h: o.height };
      moved = true;
    }
    const el = copyRef.current;
    if (!el) {
      copyBox.current = null;
      return moved;
    }
    const b = el.getBoundingClientRect();
    const box = {
      left: b.left - o.left,
      right: b.right - o.left,
      top: b.top - o.top,
      bottom: b.bottom - o.top,
    };
    const prev = copyBox.current;
    if (
      prev &&
      prev.left === box.left &&
      prev.right === box.right &&
      prev.top === box.top &&
      prev.bottom === box.bottom
    ) {
      return moved;
    }
    copyBox.current = box;
    return true;
  };

  const place = (clock: number): PlacedSheet[] => {
    const box = fieldBox.current;
    const vw = box?.w ?? 1440;
    const vh = box?.h ?? 800;
    const out: PlacedSheet[] = [];
    const placed: { cx: number; cy: number; r: number }[] = [];
    const hitsCopy = (cx: number, cy: number, r: number) => {
      const c = copyBox.current;
      if (!c) return false;
      const nx = Math.max(c.left, Math.min(cx, c.right));
      const ny = Math.max(c.top, Math.min(cy, c.bottom));
      return Math.hypot(cx - nx, cy - ny) < r;
    };

    SPLASH_LAYOUT.forEach((s, i) => {
      const size = s.size * sheetScale;
      const r = size * 0.46;
      const cx = (parseFloat(s.x) / 100) * vw;
      const cy = (parseFloat(s.y) / 100) * vh;
      const clear =
        placed.every((o) => Math.hypot(cx - o.cx, cy - o.cy) >= r + o.r + minGap) &&
        !hitsCopy(cx, cy, r + minGap);
      if (!clear) return;
      const off = s.off * spread;
      const result = reduced
        ? splashPathsAt(0.6, frames)
        : splashPathsAt(clock + off, frames);
      const paths = result.paths.map((p) => ({
        d: p.d,
        fill:
          p.fill === "#ffffff"
            ? "#ffffff"
            : PASTEL_SHEET_COLOURS[
                (PASTEL_SHEET_COLOURS.indexOf(p.fill as (typeof PASTEL_SHEET_COLOURS)[number]) +
                  i) %
                  PASTEL_SHEET_COLOURS.length
              ]!,
      }));
      placed.push({ cx, cy, r });
      out.push({
        x: s.x,
        y: s.y,
        sizePx: Math.round(size),
        opacity: s.opacity,
        off,
        layoutIndex: i,
        paths,
        degrees: result.degrees,
      });
    });
    return out;
  };

  useEffect(() => {
    const onResize = () => {
      if (measure()) setSheets(place(0));
    };
    window.addEventListener("resize", onResize);
    const t = window.setTimeout(() => {
      if (measure()) setSheets(place(0));
    }, 120);
    void document.fonts?.ready.then(() => {
      if (measure()) setSheets(place(0));
    });

    // Initial placement happens on the first animation frame (before paint),
    // for the reduced (static) case as a single frame.
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      measure();
      setSheets(place(((now - start) / 1000) * foldSpeed));
      if (!reduced) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      window.clearTimeout(t);
    };
  }, [foldSpeed, spread, sheetScale, minGap, reduced]);

  return (
    <div
      id="splash-field"
      ref={fieldRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      {sheets.map((s) => (
        <svg
          key={`${s.x}-${s.y}-${s.layoutIndex}`}
          viewBox="-115 -115 230 230"
          className="absolute overflow-visible"
          style={{
            left: s.x,
            top: s.y,
            width: s.sizePx,
            height: s.sizePx,
            transform: "translate(-50%, -50%)",
            opacity: s.opacity,
          }}
        >
          <g transform={`rotate(${s.degrees.toFixed(2)})`}>
            {s.paths.map((p) => (
              <path key={`${p.fill}-${p.d}`} d={p.d} fill={p.fill} />
            ))}
          </g>
        </svg>
      ))}
    </div>
  );
}
