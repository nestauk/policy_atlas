import { cn } from "../../../ui/brand/cn";
import { ArrowDownIcon } from "../../../ui/brand/icons";

/** The way back to the end of a transcript once the reader has scrolled up:
 *  a square button floating over the scroll region's bottom edge (owner request,
 *  2026-09-05). Render it inside a `relative` wrapper around the region. */
export function JumpToEnd({ visible, onClick }: { visible: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Jump to the end"
      aria-hidden={!visible}
      tabIndex={visible ? 0 : -1}
      title="Jump to the end"
      className={cn(
        "pressable absolute bottom-3 left-1/2 z-10 flex h-8 w-8 -translate-x-1/2 items-center justify-center border border-line bg-paper text-navy shadow-[0_10px_30px_rgba(15,41,74,0.14)] hover:border-blue hover:text-blue",
        "transition-[opacity,transform] duration-150 ease-[var(--ease-out-strong)]",
        visible ? "opacity-100" : "pointer-events-none translate-y-2 opacity-0",
      )}
    >
      <ArrowDownIcon />
    </button>
  );
}
