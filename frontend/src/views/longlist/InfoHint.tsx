import { Anchor as PopoverAnchor } from "@radix-ui/react-popover";
import { useRef, useState } from "react";

import { InfoIcon } from "../../ui/brand/icons";
import { Popover, PopoverContent } from "../../ui/radix/Popover";
import { Tooltip, TooltipProvider } from "../../ui/radix/Tooltip";

/**
 * A small "i" whose words say what something is (round 12, owner): a 16 px
 * glyph from the icon module in a 24 px target, Grey turning Navy on a Blue
 * Wash, the help cursor, focusable. One component, two paths: hover and
 * keyboard focus open the tooltip; a tap (a touch press, where a tooltip
 * never opens) opens the same words as a small popover in the popover's
 * tokens, and a second tap, Escape or a press outside closes it. The option
 * card's estimate and the longlist's Group by use it.
 *
 * Args:
 *   label: The button's name.
 *   note: The words; several are one line each.
 */
export function InfoHint({ label, note }: { label: string; note: string | readonly string[] }) {
  const lines = typeof note === "string" ? [note] : note;
  const words = lines.map((line) => <p key={line}>{line}</p>);
  const [tapped, setTapped] = useState(false);
  // The press that led to this click was a touch.
  const touch = useRef(false);
  return (
    <Popover open={tapped} onOpenChange={setTapped}>
      <PopoverAnchor asChild>
        <span className="inline-flex">
          <TooltipProvider delayDuration={200}>
            <Tooltip content={words}>
              <button
                type="button"
                aria-label={label}
                onPointerDown={(event) => {
                  touch.current = event.pointerType === "touch";
                }}
                onClick={() => {
                  if (touch.current) setTapped((open) => !open);
                  touch.current = false;
                }}
                className="pressable inline-flex size-6 shrink-0 cursor-help items-center justify-center text-grey transition-colors duration-150 hover:bg-blue-tint-2 hover:text-navy"
              >
                <InfoIcon />
              </button>
            </Tooltip>
          </TooltipProvider>
        </span>
      </PopoverAnchor>
      <PopoverContent
        align="start"
        aria-label={label}
        className="w-auto max-w-[min(20rem,92vw)] space-y-1 p-3"
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        {words}
      </PopoverContent>
    </Popover>
  );
}
