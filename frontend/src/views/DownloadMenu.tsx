import { useState } from "react";

import { cn } from "../ui/brand/cn";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";

export interface DownloadItem {
  label: string;
  /** A grey line under the label: what the file is for. */
  hint?: string;
  /** A heading over this item and the ones after it. */
  group?: string;
  onSelect: () => void;
}

/** The "Download" button and its menu: the ES report's and the theory canvas's. */
export function DownloadMenu({ items, small = false }: { items: DownloadItem[]; small?: boolean }) {
  const [open, setOpen] = useState(false);
  const grouped = items.some((item) => item.group !== undefined);
  return (
    <div className="print-hide shrink-0">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            className={cn(
              "inline-flex cursor-pointer items-center gap-2 border border-navy bg-paper font-semibold text-navy hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue",
              small ? "px-2.5 py-[5px] text-meta" : "px-3 py-2 text-body",
            )}
          >
            Download
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </PopoverTrigger>
        <PopoverContent align="end" className={cn("p-0", items.some((item) => item.hint) ? "w-72" : "w-44")}>
          <ul role="menu" className="flex flex-col py-1">
            {items.map((item, index) => (
              <li key={item.label} role="none">
                {index > 0 && (item.group !== undefined || !grouped) && <div className="border-t border-line" />}
                {item.group !== undefined && (
                  <p role="presentation" className="px-3 pt-2.5 text-caption font-bold uppercase tracking-wide text-grey">
                    {item.group}
                  </p>
                )}
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpen(false);
                    item.onSelect();
                  }}
                  className="block w-full cursor-pointer px-3 py-2.5 text-left text-body text-navy hover:bg-blue-tint-2 hover:text-blue"
                >
                  <span className={cn("block", item.hint !== undefined && "font-semibold")}>{item.label}</span>
                  {item.hint !== undefined && <span className="block text-meta text-grey">{item.hint}</span>}
                </button>
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>
    </div>
  );
}
