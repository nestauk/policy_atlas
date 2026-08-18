import { useState } from "react";

import { cn } from "../ui/brand/cn";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import {
  artefactMarkdown,
  downloadFilename,
  triggerTextDownload,
} from "./artefactPresentation";

/**
 * Report download: PDF via the existing print stylesheet, markdown as a
 * file. Word is skipped — it needs a library this slice does not add.
 */
export function ArtefactDownload({
  artefact,
}: {
  artefact: Parameters<typeof artefactMarkdown>[0];
}) {
  const [open, setOpen] = useState(false);

  const downloadMarkdown = () => {
    setOpen(false);
    triggerTextDownload(
      downloadFilename(artefact.title, "md"),
      artefactMarkdown(artefact),
      "text/markdown",
    );
  };

  const downloadPdf = () => {
    setOpen(false);
    window.setTimeout(() => window.print(), 0);
  };

  return (
    <div className="print-hide shrink-0">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            className="inline-flex cursor-pointer items-center gap-2 border border-navy bg-paper px-3 py-2 text-body font-semibold text-navy hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
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
        <PopoverContent align="end" className="w-44 p-0">
          <ul role="menu" className="flex flex-col py-1">
            {(
              [
                ["PDF", downloadPdf],
                ["Markdown", downloadMarkdown],
              ] as const
            ).map(([label, onSelect], index) => (
              <li key={label} role="none">
                {index > 0 && <div className="border-t border-line" />}
                <button
                  type="button"
                  role="menuitem"
                  onClick={onSelect}
                  className={cn(
                    "block w-full cursor-pointer px-3 py-2.5 text-left text-body text-navy hover:bg-blue-tint-2 hover:text-blue",
                  )}
                >
                  {label}
                </button>
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>
    </div>
  );
}
