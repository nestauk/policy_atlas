import type { ReactNode } from "react";

import { blobUrl } from "../../lib/blobUrl";

// The user's own theory-of-change diagram (task 054, increment 5): the paperclip that picks it, and its preview.

/**
 * The paperclip: an attached diagram. Drawn as `ui/brand/icons.tsx` draws (a
 * 16-unit grid, the 1.5 stroke, round joins, `currentColor`); it belongs in
 * that module once it serves a second view.
 */
export function PaperclipGlyph({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg aria-hidden="true" focusable="false" width={size} height={size} viewBox="0 0 16 16" className={className} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="m14 7.33-5.67 5.67a3.33 3.33 0 0 1-4.67-4.67L9.33 2.67a2.33 2.33 0 0 1 3.33 3.33l-5.67 5.67a1.33 1.33 0 0 1-2-2L10 4.67" />
    </svg>
  );
}

/** A paperclip label that opens the file picker for a PNG, JPEG or PDF diagram. */
export function AttachFileButton({
  onFile,
  disabled = false,
  title,
  className,
  iconClassName,
  children,
}: {
  onFile: (file: File) => void;
  disabled?: boolean;
  title?: string;
  className: string;
  iconClassName: string;
  children: ReactNode;
}) {
  return (
    <label title={title} className={className}>
      <PaperclipGlyph className={iconClassName} />
      {children}
      <input
        type="file"
        accept="image/png,image/jpeg,application/pdf"
        disabled={disabled}
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file !== undefined) onFile(file);
        }}
      />
    </label>
  );
}

/** An uploaded diagram: the picture, linked full size; a PDF as the caller words it. */
export function UploadPreview({ blob, pdf, className, imageClassName }: { blob: Blob; pdf: (url: string) => ReactNode; className?: string; imageClassName: string }) {
  const url = blobUrl(blob);
  return blob.type === "application/pdf" ? (
    pdf(url)
  ) : (
    <a href={url} target="_blank" rel="noreferrer" title="Open full size" className={className}>
      <img src={url} alt="Your theory of change, as uploaded" className={imageClassName} />
    </a>
  );
}
