import { useCallback, useRef, useState } from "react";

import { cn } from "../../ui/brand/cn";

/** Resize bounds (px). Below MIN the plan pane's chips wrap unreadably; above
 *  MAX the analysis column loses the room the journey cards need at 1280. */
const RAIL_MIN = 280;
const RAIL_MAX = 640;
const KEY_STEP = 24;
/** Collapsed strip: just the expand control, nothing readable. */
const RAIL_COLLAPSED = "48px";

export interface RailState {
  collapsed: boolean;
  /** Value for the workspace grid's chat-column width variable. */
  width: string;
  toggleProps: {
    "aria-expanded": boolean;
    "aria-controls": string;
    onClick: () => void;
  };
  /** Spread onto the drag/keyboard separator between the columns. */
  separatorProps: {
    role: "separator";
    "aria-orientation": "vertical";
    "aria-label": string;
    "aria-valuemin": number;
    "aria-valuemax": number;
    "aria-valuenow": number | undefined;
    tabIndex: 0;
    onPointerDown: (event: React.PointerEvent<HTMLElement>) => void;
    onKeyDown: (event: React.KeyboardEvent<HTMLElement>) => void;
  };
  /** id the collapsible region must carry (aria-controls target). */
  regionId: string;
}

/**
 * Session-local state for the collapsible/resizable planning rail
 * (027 strand 3; PR #35's IDE-style rail, single-thread). Collapse is a real
 * button — keyboard-operable by construction (finding 19) — and resize is a
 * `role="separator"` handle that works by pointer drag or arrow keys, clamped
 * to sane bounds. No persistence: a fresh session gets the default split.
 *
 * Until the user resizes, the width stays on the caller's animated
 * percentage default (the 55/45→35/65 RETRO split); the first resize pins it
 * to pixels for the rest of the session.
 */
export function useRail(defaultWidth: string): RailState {
  const [collapsed, setCollapsed] = useState(false);
  const [px, setPx] = useState<number | null>(null);
  const dragFrom = useRef<{ x: number; width: number } | null>(null);

  const clamp = (value: number) => Math.min(Math.max(value, RAIL_MIN), RAIL_MAX);

  const onPointerDown = useCallback((event: React.PointerEvent<HTMLElement>) => {
    const column = (event.currentTarget as HTMLElement).parentElement;
    if (column === null) return;
    dragFrom.current = { x: event.clientX, width: column.getBoundingClientRect().width };
    const handle = event.currentTarget as HTMLElement;
    handle.setPointerCapture(event.pointerId);
    const onMove = (move: PointerEvent) => {
      const from = dragFrom.current;
      if (from === null) return;
      setPx(clamp(from.width + (move.clientX - from.x)));
    };
    const onUp = () => {
      dragFrom.current = null;
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
    };
    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
  }, []);

  const onKeyDown = useCallback((event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const column = (event.currentTarget as HTMLElement).parentElement;
    const current = column?.getBoundingClientRect().width ?? RAIL_MIN;
    setPx(clamp(current + (event.key === "ArrowRight" ? KEY_STEP : -KEY_STEP)));
  }, []);

  return {
    collapsed,
    width: collapsed ? RAIL_COLLAPSED : px !== null ? `${px}px` : defaultWidth,
    regionId: "planning-rail",
    toggleProps: {
      "aria-expanded": !collapsed,
      "aria-controls": "planning-rail",
      onClick: () => setCollapsed((value) => !value),
    },
    separatorProps: {
      role: "separator",
      "aria-orientation": "vertical",
      "aria-label": "Resize the planning rail",
      "aria-valuemin": RAIL_MIN,
      "aria-valuemax": RAIL_MAX,
      "aria-valuenow": px ?? undefined,
      tabIndex: 0,
      onPointerDown,
      onKeyDown,
    },
  };
}

/** The chevron toggle rendered at the top of the rail (and as the whole
 *  collapsed strip's control). A real `<button>` with an honest name. */
export function RailToggle({
  collapsed,
  toggleProps,
  className,
}: {
  collapsed: boolean;
  toggleProps: RailState["toggleProps"];
  className?: string;
}) {
  return (
    <button
      type="button"
      {...toggleProps}
      className={cn(
        "inline-flex h-8 w-8 cursor-pointer items-center justify-center text-grey",
        "hover:bg-ground hover:text-navy",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue",
        className,
      )}
    >
      <span aria-hidden="true">{collapsed ? "»" : "«"}</span>
      <span className="sr-only">
        {collapsed ? "Expand the planning rail" : "Collapse the planning rail"}
      </span>
    </button>
  );
}
