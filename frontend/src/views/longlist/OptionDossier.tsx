import { useFindings, useSourceDossier } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { Sheet, SheetContent } from "../../ui/radix/Sheet";
import { SourceDossierBody, useDossierRecords } from "../SourcesView";

/**
 * A document's dossier over the option card (round 12, owner bug: a
 * document opened the Sources tab). The Sources tab's sheet, read by the
 * document's id, its slot reading "In this option"; the reader stays on the
 * card, and closing returns to it.
 *
 * Args:
 *   taskId: The scoping task.
 *   sourceId: The document's id (its `task_source_snapshot_id`).
 *   optionId: The option whose card opened it.
 *   onClose: Called when the sheet closes.
 */
export function OptionDossier({
  taskId,
  sourceId,
  optionId,
  onClose,
}: {
  taskId: string;
  sourceId: string;
  optionId: string;
  onClose: () => void;
}) {
  const dossier = useSourceDossier(taskId, sourceId);
  const findings = useFindings(taskId, { page_size: 200, source_id: sourceId });
  const records = useDossierRecords(taskId, sourceId, optionId);
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent title={dossier.data ? scrub(dossier.data.title) : "Source dossier"}>
        {dossier.isPending && (
          <p role="status" className="anim-breathe-soft text-body text-grey">
            Loading the dossier…
          </p>
        )}
        {dossier.isError && (
          <p role="alert" className="text-body text-navy">
            This source dossier couldn't be loaded.
          </p>
        )}
        {dossier.data && (
          <SourceDossierBody
            records={records}
            source={dossier.data}
            findings={findings.data?.data}
            findingsPending={findings.isPending}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}
