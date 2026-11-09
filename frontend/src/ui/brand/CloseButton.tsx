import type { ButtonHTMLAttributes } from "react";

import { cn } from "./cn";
import { CloseIcon, iconButtonClass } from "./icons";

type CloseButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  /** The control's accessible name ("Close panel", "Dismiss"). */
  "aria-label": string;
  /** `onRed` for the sensitive-information banner: white glyph, white ring. */
  tone?: "default" | "onRed";
};

/**
 * The one close control (task 058 consistency pass; DESIGN.md § Buttons,
 * Close): the chrome icon button, a 16 px × in a 32 px square, Grey turning
 * Navy over Blue Wash, the 3% press and the house focus ring. Sheets, toasts,
 * the find dialog and the banner all close with it. Spreads its props onto
 * the `<button>`, so a Radix `Close asChild` can wrap it.
 */
export function CloseButton({ className, tone = "default", type, ...props }: CloseButtonProps) {
  return (
    <button
      type={type ?? "button"}
      className={cn(
        iconButtonClass("chrome"),
        tone === "onRed" &&
          "text-white hover:bg-white/15 hover:text-white focus-visible:outline-white",
        className,
      )}
      {...props}
    >
      <CloseIcon />
    </button>
  );
}
