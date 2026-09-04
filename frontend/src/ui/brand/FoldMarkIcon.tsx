import type { SVGAttributes } from "react";

import { BLUE, BRAND_MARK_SIZE, BRAND_MARK_VIEWBOX, STATIC_LOGO_FRAME, framePaths } from "./foldMark";
import { cn } from "./cn";

/**
 * Static fold-mark logo — prototype frame 5 (all corners folded, solid blue diamond).
 *
 * @param size - Width and height in CSS pixels.
 * @param reverse - Fold reverse colour; defaults to hero blue so the mark
 *   reads on both navy (splash) and paper (app nav).
 */
export function FoldMarkIcon({
  size = BRAND_MARK_SIZE,
  reverse = BLUE,
  className,
  ...props
}: {
  size?: number;
  reverse?: string;
} & SVGAttributes<SVGSVGElement>) {
  const paths = framePaths(STATIC_LOGO_FRAME, undefined, reverse);
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox={BRAND_MARK_VIEWBOX}
      className={cn("shrink-0 overflow-visible", className)}
      {...props}
    >
      {paths.map((p) => (
        <path key={p.d} d={p.d} fill={p.fill} />
      ))}
    </svg>
  );
}
