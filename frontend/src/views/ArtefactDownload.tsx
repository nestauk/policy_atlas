import { DownloadMenu } from "./DownloadMenu";
import {
  artefactMarkdown,
  downloadFilename,
  triggerTextDownload,
} from "./artefactPresentation";

/**
 * Report download: PDF via the existing print stylesheet, markdown as a
 * file. Word is skipped — it needs a library this slice does not add.
 * The Markdown is headed with the question, as the page is; the generated
 * title names the file (task 058, round 10, D1).
 */
export function ArtefactDownload({
  artefact,
  question = null,
}: {
  artefact: Parameters<typeof artefactMarkdown>[0];
  /** The task's question, the page's title; null keeps the artefact's own. */
  question?: string | null;
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
              artefactMarkdown(artefact, question),
              "text/markdown",
            ),
        },
      ]}
    />
  );
}
