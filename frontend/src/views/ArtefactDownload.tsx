import { DownloadMenu } from "./DownloadMenu";
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
  return (
    <DownloadMenu
      items={[
        // Expand handlers on sections listen for `beforeprint` and flushSync
        // their open state; print then captures the full report.
        { label: "PDF", onSelect: () => window.print() },
        {
          label: "Markdown",
          onSelect: () =>
            triggerTextDownload(
              downloadFilename(artefact.title, "md"),
              artefactMarkdown(artefact),
              "text/markdown",
            ),
        },
      ]}
    />
  );
}
