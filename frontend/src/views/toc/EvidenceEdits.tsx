import { useState } from "react";

import type { components } from "../../api/gen/types";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { DocumentItem } from "./Documents";
import type { Editor } from "./Editing";
import { SUPPORT_LABEL } from "./tocModel";
import type { Support, TocDocument, TocGraph, TocLink } from "./types";

const SUPPORTS: Support[] = ["strong", "weak", "mixed", "refutes", "not_about"];
const PILL = "cursor-pointer rounded-full border px-2.5 py-0.5 text-meta";

/** A document's Change menu: the user's support and relevance, back to the judge's, or remove (C42). */
export function DocumentActions({ doc, editor }: { doc: TocDocument; editor: Editor }) {
  const [open, setOpen] = useState(false);
  const [support, setSupport] = useState<Support>(doc.support);
  const [relevance, setRelevance] = useState(doc.relevance);
  const patch = (body: components["schemas"]["TocEvidencePatch"], done: string) =>
    editor.run({ kind: "evidence", evidenceId: doc.evidence_id, body }, done, () => setOpen(false));
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="mt-1 cursor-pointer text-meta font-semibold text-blue hover:underline">
        Change
      </button>
    );
  }
  return (
    <div role="group" aria-label="Change this document" className="mt-2 rounded-lg border border-line-2 bg-paper px-3 py-2.5 shadow-sm">
      <p className="text-meta font-bold text-ink">Your scores</p>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {SUPPORTS.map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={support === item}
            onClick={() => setSupport(item)}
            className={`${PILL} ${support === item ? "border-blue bg-blue-tint font-bold text-blue" : "border-line-2 text-ink"}`}
          >
            {SUPPORT_LABEL[item]}
          </button>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1">
        <span className="mr-1 text-meta text-ink">Relevance</span>
        {[0, 1, 2, 3].map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={relevance === item}
            aria-label={`Relevance ${item}`}
            onClick={() => setRelevance(item)}
            className={`${PILL} ${relevance === item ? "border-blue bg-blue-tint font-bold text-blue" : "border-line-2 text-ink"}`}
          >
            {item}
          </button>
        ))}
      </div>
      {doc.judge_support != null && (
        <p className="mt-2 text-meta text-grey">
          Judge said: {SUPPORT_LABEL[doc.judge_support]} · relevance {doc.judge_relevance}
        </p>
      )}
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={editor.busy} onClick={() => patch({ expected_revision: doc.revision, action: "score", support, relevance }, "Changed the scores")}>
          Save
        </Button>
        {doc.scored_by != null && (
          <Button size="sm" variant="secondary" disabled={editor.busy} onClick={() => patch({ expected_revision: doc.revision, action: "unscore" }, "Back to the judge's scores")}>
            Use the judge's scores
          </Button>
        )}
        <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>
          Cancel
        </Button>
        <span className="flex-1" />
        <button
          type="button"
          disabled={editor.busy}
          onClick={() => patch({ expected_revision: doc.revision, action: "remove" }, "Removed a study")}
          className="cursor-pointer text-meta font-bold text-[var(--color-verdict-against-text)] hover:underline"
        >
          Remove from this connection
        </button>
      </div>
    </div>
  );
}

/** Documents the user removed: listed greyed, with Restore (C42). */
export function RemovedDocuments({ documents, editor }: { documents: TocDocument[]; editor: Editor | null }) {
  const removed = documents.filter((doc) => doc.removed_by != null);
  if (removed.length === 0) return null;
  return (
    <>
      <p className="mt-3 text-body font-bold text-ink">Removed ({removed.length})</p>
      <ul>
        {removed.map((doc) => (
          <DocumentItem
            key={doc.evidence_id}
            muted
            title={doc.title}
            url={doc.url}
            quote={null}
            chips={`Removed by ${doc.removed_by}`}
            authors={doc.authors}
            source_type={doc.source_type}
            year={doc.year}
            evidence_type={doc.evidence_type}
            actions={
              editor !== null && (
                <button
                  type="button"
                  disabled={editor.busy}
                  onClick={() => editor.run({ kind: "evidence", evidenceId: doc.evidence_id, body: { expected_revision: doc.revision, action: "restore" } }, "Restored a study")}
                  className="mt-1 cursor-pointer text-meta font-semibold text-blue hover:underline"
                >
                  Restore
                </button>
              )
            }
          />
        ))}
      </ul>
    </>
  );
}

/** Add a study by its DOI: Policy Atlas fetches, judges and adds it (C42). */
export function AddStudy({ link, editor, running }: { link: TocLink; editor: Editor; running: boolean }) {
  const [value, setValue] = useState("");
  return (
    <form
      aria-label="Add a study"
      className="mt-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (value.trim() === "") return;
        editor.run({ kind: "addStudy", linkId: link.link_id, body: { identifier: value.trim() } }, undefined, () => setValue(""));
      }}
    >
      <p className="text-body font-bold text-ink">Add a study</p>
      <div className="mt-1 flex gap-2">
        <input
          aria-label="DOI"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="DOI, e.g. 10.1016/j.appet.2016.02.017"
          className="min-w-0 flex-1 border border-line-2 bg-paper px-2 py-1.5 text-body"
        />
        <Button type="submit" size="sm" variant="secondary" disabled={editor.busy || running || value.trim() === ""}>
          Add
        </Button>
      </div>
      <p className="mt-1 text-meta text-grey">Policy Atlas fetches it, judges it for this connection and adds it, marked as added by you.</p>
    </form>
  );
}

/** After an edit: the evidence is from the earlier wording. Keep it or check again (C43). */
export function EditedEvidenceBlock({ link, graph, editor }: { link: TocLink; graph: TocGraph; editor: Editor | null }) {
  const running = graph.check_status === "drafting" || graph.check_status === "checking";
  if (link.state === "kept") {
    return <p className="mt-2 text-meta text-grey">Evidence kept for the new wording{link.edited_by != null ? ` by ${scrub(link.edited_by)}` : ""}.</p>;
  }
  if (link.state !== "pending") return null;
  return (
    <div className="mt-3 border-l-[3px] border-blue bg-blue-tint-2 px-3 py-2.5">
      <p className="text-body font-bold text-ink">Evidence from the earlier wording</p>
      <p className="text-body">This connection or a box at either end changed. Its evidence was judged for the earlier wording.</p>
      {editor !== null && (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" disabled={editor.busy} onClick={() => editor.run({ kind: "keep", body: { link_ids: [link.link_id] } }, "Kept the evidence")}>
            Keep the evidence
          </Button>
          <Button
            size="sm"
            disabled={editor.busy || running}
            onClick={() => editor.run({ kind: "check", body: { link_ids: [link.link_id], mode: "check_again" } })}
          >
            {running ? "A check is running" : "Check again"}
          </Button>
        </div>
      )}
    </div>
  );
}
