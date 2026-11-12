import { useCallback, useRef, useState } from "react";

/** Resize bounds (px) — the workspace rail's own clamp. */
const PANEL_MIN = 280;
const PANEL_MAX = 640;
const KEY_STEP = 24;

/**
 * Drag/keyboard width for a side panel. The handle sits on the panel's
 * right edge by default (the chat panel, on the left of the view); with
 * `edge: "left"` it sits on the left edge (a panel on the right of the view),
 * so dragging left widens it.
 */
export function usePanelWidth({ label, initial, edge = "right" }: { label: string; initial: number; edge?: "left" | "right" }) {
  const [px, setPx] = useState(initial);
  const dragFrom = useRef<{ x: number; width: number } | null>(null);
  const clamp = (value: number) => Math.min(Math.max(value, PANEL_MIN), PANEL_MAX);
  const sign = edge === "right" ? 1 : -1;

  const onPointerDown = useCallback((event: React.PointerEvent<HTMLElement>) => {
    const panel = (event.currentTarget as HTMLElement).parentElement;
    if (panel === null) return;
    dragFrom.current = { x: event.clientX, width: panel.getBoundingClientRect().width };
    const handle = event.currentTarget as HTMLElement;
    handle.setPointerCapture(event.pointerId);
    const onMove = (move: PointerEvent) => {
      const from = dragFrom.current;
      if (from === null) return;
      setPx(clamp(from.width + sign * (move.clientX - from.x)));
    };
    const onUp = () => {
      dragFrom.current = null;
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
    };
    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
  }, [sign]);

  const onKeyDown = useCallback((event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    setPx((current) => clamp(current + sign * (event.key === "ArrowRight" ? KEY_STEP : -KEY_STEP)));
  }, [sign]);

  return {
    width: `${px}px`,
    separatorProps: {
      role: "separator" as const,
      "aria-orientation": "vertical" as const,
      "aria-label": label,
      "aria-valuemin": PANEL_MIN,
      "aria-valuemax": PANEL_MAX,
      "aria-valuenow": px,
      tabIndex: 0 as const,
      onPointerDown,
      onKeyDown,
    },
  };
}

export type PanelWidth = ReturnType<typeof usePanelWidth>;
