import { cn } from "../../../ui/brand/cn";
import { ArrowDownIcon } from "./icons";

/** The way back to the end of a transcript once the reader has scrolled up:
 *  a pill floating over the scroll region's bottom edge (owner request,
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
        "pressable absolute bottom-3 left-1/2 z-10 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-line bg-paper text-navy shadow-sm hover:border-blue hover:text-blue focus-visible:outline-2 focus-visible:outline-blue",
        "transition-[opacity,transform] duration-150",
        visible ? "opacity-100" : "pointer-events-none translate-y-2 opacity-0",
      )}
    >
      <ArrowDownIcon size={16} />
    </button>
  );
}
