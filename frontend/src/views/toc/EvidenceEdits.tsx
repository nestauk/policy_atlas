import { useState } from "react";

import type { components } from "../../api/gen/types";
import { scrub } from "../../lib/scrub";
import { ACTION_CONTROL_CLASS, ActionGlyph, WithTooltip } from "../../ui/brand/actionControls";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { QUIET_CONTROL_CLASS } from "../../ui/brand/inlineActions";
import { OutlineSwitch } from "../../ui/brand/OutlineSwitch";
import { Select } from "../../ui/brand/Select";
import { DocumentItem, VerdictWords } from "./Documents";
import { CheckButton, type Editor, FIELD_CLASS, FIELD_LABEL_CLASS } from "./Editing";
import { SUPPORT_LABEL } from "./tocModel";
import type { Support, TocDocument, TocGraph, TocLink } from "./types";

const SUPPORTS: Support[] = ["strong", "weak", "mixed", "refutes", "not_about"];
const SUPPORT_OPTIONS = SUPPORTS.map((value) => ({ value, label: SUPPORT_LABEL[value] }));
const RELEVANCE_CHOICES = (["0", "1", "2", "3"] as const).map((key) => ({ key, label: key }));

/** What the document controls do, on hover and focus (owner, 2026-11-09). */
const REMOVE_TOOLTIP = "Leave this document out of this connection's evidence.";
const RESTORE_TOOLTIP = "Count this document in this connection's evidence again.";

/** "Remove" or "Restore" on a document (owner, 2026-11-09): the colleague's
 *  words in the quiet control with the glyph before them, as the longlist's
 *  Exclude and Include again; grey, never red. */
function DocumentToggle({ restore, disabled, onClick }: { restore: boolean; disabled: boolean; onClick: () => void }) {
  return (
    <WithTooltip note={restore ? RESTORE_TOOLTIP : REMOVE_TOOLTIP}>
      <button type="button" disabled={disabled} onClick={onClick} className={ACTION_CONTROL_CLASS}>
        <ActionGlyph include={restore} />
        {restore ? "Restore" : "Remove"}
      </button>
    </WithTooltip>
  );
}

/** A document's Change menu: the user's support and relevance, back to the judge's, or remove (C42). */
export function DocumentActions({ doc, editor }: { doc: TocDocument; editor: Editor }) {
  const [open, setOpen] = useState(false);
  const [support, setSupport] = useState<Support>(doc.support);
  const [relevance, setRelevance] = useState(doc.relevance);
  const patch = (body: components["schemas"]["TocEvidencePatch"], done: string) =>
    editor.run({ kind: "evidence", evidenceId: doc.evidence_id, body }, done, () => setOpen(false));
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={cn(QUIET_CONTROL_CLASS, "mt-1 text-meta")}>
        Change
      </button>
    );
  }
  return (
    <div role="group" aria-label="Change this document" className="mt-2 border border-line-2 bg-paper px-3 py-2.5">
      <p className="text-meta font-bold text-ink">Your scores</p>
      <div className="mt-2 grid gap-1">
        <span aria-hidden="true" className={FIELD_LABEL_CLASS}>
          Support
        </span>
        <Select label="Support" size={32} value={support} options={SUPPORT_OPTIONS} onChange={setSupport} className="w-full" />
      </div>
      <div className="mt-2 grid justify-items-start gap-1">
        <span aria-hidden="true" className={FIELD_LABEL_CLASS}>
          Relevance
        </span>
        <OutlineSwitch label="Relevance" height={32} choices={RELEVANCE_CHOICES} value={String(relevance) as (typeof RELEVANCE_CHOICES)[number]["key"]} onChange={(key) => setRelevance(Number(key))} />
      </div>
      {doc.judge_support != null && (
        <p className="mt-2 text-meta text-grey">
          Judge said: {SUPPORT_LABEL[doc.judge_support]} · relevance {doc.judge_relevance}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-3">
        <Button variant="outline" size="sm" disabled={editor.busy} onClick={() => patch({ expected_revision: doc.revision, action: "score", support, relevance }, "Changed the scores")}>
          Save
        </Button>
        {doc.scored_by != null && (
          <Button size="sm" variant="secondary" disabled={editor.busy} onClick={() => patch({ expected_revision: doc.revision, action: "unscore" }, "Back to the judge's scores")}>
            Use the judge's scores
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
        <span className="flex-1" />
        <DocumentToggle restore={false} disabled={editor.busy} onClick={() => patch({ expected_revision: doc.revision, action: "remove" }, "Removed a study")} />
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
            doc={doc}
            muted
            quote={null}
            chips={`Removed by ${doc.removed_by}`}
            actions={
              editor !== null && (
                <span className="mt-1 flex">
                  <DocumentToggle
                    restore
                    disabled={editor.busy}
                    onClick={() => editor.run({ kind: "evidence", evidenceId: doc.evidence_id, body: { expected_revision: doc.revision, action: "restore" } }, "Restored a study")}
                  />
                </span>
              )
            }
          />
        ))}
      </ul>
    </>
  );
}

/** Add a study by its DOI: Policy Atlas fetches, judges and adds it (C42). */
export function AddStudy({ link, editor }: { link: TocLink; editor: Editor }) {
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
      <div className="mt-1.5 flex gap-2">
        <input
          aria-label="DOI"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="DOI, e.g. 10.1016/j.appet.2016.02.017"
          className={cn(FIELD_CLASS, "h-10 flex-1 py-0 text-body")}
        />
        <Button type="submit" variant="outline" className="h-10 py-0" disabled={editor.busy || value.trim() === ""}>
          Add
        </Button>
      </div>
    </form>
  );
}

/** After an edit: the evidence is from the earlier wording. Keep it or check again (C43). */
export function EditedEvidenceBlock({ link, graph, editor }: { link: TocLink; graph: TocGraph; editor: Editor | null }) {
  if (link.state === "kept") {
    return <p className="mt-2 text-body text-grey">Evidence kept for the new wording{link.edited_by != null ? ` by ${scrub(link.edited_by)}` : ""}.</p>;
  }
  if (link.state !== "pending") return null;
  return (
    <div className="mt-3 border-l-2 border-blue bg-blue-tint-2 px-3 py-2.5">
      <p className="text-body font-bold text-ink">Evidence from the earlier wording</p>
      <p className="text-body">This connection or a box at either end changed. Its evidence was judged for the earlier wording.</p>
      {editor !== null && (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={editor.busy} onClick={() => editor.run({ kind: "keep", body: { link_ids: [link.link_id] } }, "Kept the evidence")}>
            Keep the evidence
          </Button>
          <CheckButton graph={graph} editor={editor} ids={[link.link_id]} mode="check_again" label="Check again" />
        </div>
      )}
    </div>
  );
}

/** New evidence from Find more evidence: nothing counts until accepted (C44). */
export function NewEvidenceBlock({ link, documents, editor }: { link: TocLink; documents: TocDocument[]; editor: Editor | null }) {
  const pending = documents.filter((doc) => doc.status === "pending");
  if (pending.length === 0) return null;
  return (
    <div className="mt-3 border-l-2 border-blue bg-blue-tint-2 px-3 py-2.5">
      <p className="text-body font-bold text-ink">
        New evidence found: {pending.length} document{pending.length === 1 ? "" : "s"}
      </p>
      {link.verdict_if_accepted != null && (
        <p className="text-body">
          Verdict now: <VerdictWords verdict={link.verdict} /> → if accepted: <VerdictWords verdict={link.verdict_if_accepted} />
        </p>
      )}
      <ul>
        {pending.map((doc) => (
          <DocumentItem
            key={doc.evidence_id}
            doc={doc}
            actions={
              editor !== null && (
                <span className="mt-1.5 flex gap-2">
                  <Button size="sm" variant="outline" disabled={editor.busy} onClick={() => editor.run({ kind: "evidence", evidenceId: doc.evidence_id, body: { expected_revision: doc.revision, action: "accept" } }, "Accepted a document")}>
                    Accept
                  </Button>
                  <Button size="sm" variant="secondary" disabled={editor.busy} onClick={() => editor.run({ kind: "evidence", evidenceId: doc.evidence_id, body: { expected_revision: doc.revision, action: "reject" } }, "Rejected a document")}>
                    Reject
                  </Button>
                </span>
              )
            }
          />
        ))}
      </ul>
      {editor !== null && pending.length > 1 && (
        <div className="mt-2 flex gap-2">
          <Button size="sm" variant="outline" disabled={editor.busy} onClick={() => editor.run({ kind: "decide", linkId: link.link_id, accept: true }, "Accepted the new documents")}>
            Accept all
          </Button>
          <Button size="sm" variant="secondary" disabled={editor.busy} onClick={() => editor.run({ kind: "decide", linkId: link.link_id, accept: false }, "Rejected the new documents")}>
            Reject all
          </Button>
        </div>
      )}
    </div>
  );
}

/** Find more evidence for some links (C44): the button at the bottom of a sidebar. */
export function FindMore({ links, graph, editor }: { links: TocLink[]; graph: TocGraph; editor: Editor }) {
  const ready = links.filter((link) => link.state !== "pending" && link.state !== "unchecked");
  const ids = ready.map((link) => link.link_id);
  if (links.length === 0) return null;
  return (
    <div className="mt-5 border-t border-line pt-3">
      <CheckButton graph={graph} editor={editor} ids={ids} mode="find_more" label="Find more evidence" disabled={ready.length === 0} />
      <p className="mt-1 text-body text-grey">
        {ready.length === 0
          ? "Check this connection first: its evidence is from an earlier wording or not found yet."
          : links.length === 1
            ? "Performs a more extensive search of evidence for this connection."
            : "Performs a more extensive search of evidence for its connections."}
      </p>
    </div>
  );
}
