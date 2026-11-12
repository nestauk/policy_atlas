import type { ReactNode } from "react";

import { blobUrl } from "../../lib/blobUrl";
import { PaperclipIcon } from "../../ui/brand/icons";

// The user's own theory-of-change diagram (task 054, increment 5): the paperclip that picks it, and its preview.

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
      <PaperclipIcon className={iconClassName} />
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
