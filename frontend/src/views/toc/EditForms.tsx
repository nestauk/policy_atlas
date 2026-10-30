import { useState } from "react";

import { Button } from "../../ui/brand/Button";
import type { Editor } from "./Editing";
import { LAYER_LABEL } from "./tocModel";
import type { BoxLayer, TocBox, TocGraph, TocLink } from "./types";

const LAYERS: BoxLayer[] = ["input", "output", "outcome_short", "outcome_long", "impact", "failure_outcome"];
const INPUT = "border border-line-2 bg-paper px-2 py-1.5 text-body font-normal text-ink";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="mt-3 grid gap-1 text-meta font-semibold text-ink">
      {label}
      {children}
    </label>
  );
}

/** Delete with a second click to confirm, naming what goes with it. */
function DeleteButton({ label, confirm, onDelete, busy }: { label: string; confirm: string; onDelete: () => void; busy: boolean }) {
  const [asked, setAsked] = useState(false);
  return asked ? (
    <span className="flex items-center gap-2 text-meta">
      <span className="text-ink">{confirm}</span>
      <button type="button" disabled={busy} onClick={onDelete} className="cursor-pointer font-bold text-[var(--color-verdict-against-text)] hover:underline">
        Delete
      </button>
      <button type="button" onClick={() => setAsked(false)} className="cursor-pointer text-grey hover:underline">
        Keep
      </button>
    </span>
  ) : (
    <button type="button" onClick={() => setAsked(true)} className="cursor-pointer text-meta font-bold text-[var(--color-verdict-against-text)] hover:underline">
      {label}
    </button>
  );
}

/** Edit a box in place: every field, Save or Cancel, and Delete (C41). */
export function BoxEditForm({ box, graph, editor, onDone }: { box: TocBox; graph: TocGraph; editor: Editor; onDone: () => void }) {
  const [text, setText] = useState(box.text);
  const [layer, setLayer] = useState<BoxLayer>(box.layer);
  const [description, setDescription] = useState(box.description ?? "");
  const [definition, setDefinition] = useState(box.result_criteria.definition ?? "");
  const [indicator, setIndicator] = useState(box.result_criteria.indicator ?? "");
  const [timing, setTiming] = useState(box.result_criteria.timing ?? "");
  const links = graph.links.filter((link) => link.source_box_id === box.box_id || link.target_box_id === box.box_id).length;
  return (
    <form
      aria-label={`Edit ${box.code ?? "box"}`}
      onSubmit={(event) => {
        event.preventDefault();
        editor.run(
          {
            kind: "patchBox",
            boxId: box.box_id,
            body: {
              expected_revision: box.revision,
              text: text.trim(),
              layer,
              description: description.trim() || null,
              criteria: { definition: definition.trim() || null, indicator: indicator.trim() || null, timing: timing.trim() || null },
            },
          },
          `Edited ${box.code ?? "a box"}`,
          onDone,
        );
      }}
    >
      <p className="text-meta text-grey">Editing {box.code}</p>
      <Field label="Text">
        <textarea required value={text} onChange={(event) => setText(event.target.value)} rows={3} maxLength={500} className={INPUT} />
      </Field>
      <Field label="Layer">
        <select value={layer} onChange={(event) => setLayer(event.target.value as BoxLayer)} className={INPUT}>
          {LAYERS.map((item) => (
            <option key={item} value={item}>
              {LAYER_LABEL[item]}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Description">
        <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} maxLength={2000} className={INPUT} />
      </Field>
      <Field label="Definition">
        <input value={definition} onChange={(event) => setDefinition(event.target.value)} className={INPUT} />
      </Field>
      <Field label="Indicator">
        <input value={indicator} onChange={(event) => setIndicator(event.target.value)} className={INPUT} />
      </Field>
      <Field label="Timing">
        <input value={timing} onChange={(event) => setTiming(event.target.value)} className={INPUT} />
      </Field>
      {text.trim() !== box.text && links > 0 && (
        <p className="mt-2 text-meta text-grey">Changing the text marks its {links === 1 ? "connection" : `${links} connections`} "evidence from the earlier wording".</p>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" disabled={editor.busy || text.trim() === ""}>
          Save
        </Button>
        <Button type="button" variant="secondary" size="sm" onClick={onDone}>
          Cancel
        </Button>
        <span className="flex-1" />
        <DeleteButton
          label="Delete box"
          confirm={links > 0 ? `Also deletes ${links === 1 ? "its connection" : `its ${links} connections`}.` : "Delete this box?"}
          busy={editor.busy}
          onDelete={() => editor.run({ kind: "deleteBox", boxId: box.box_id, revision: box.revision }, `Deleted ${box.code ?? "a box"}`, onDone)}
        />
      </div>
    </form>
  );
}

/** Edit a connection in place: title, if, for, then, because, conditions; Delete (C41). */
export function LinkEditForm({ link, editor, onDone }: { link: TocLink; editor: Editor; onDone: () => void }) {
  const [title, setTitle] = useState(link.title ?? "");
  const [ifText, setIf] = useState(link.if_text);
  const [forText, setFor] = useState(link.for_text);
  const [thenText, setThen] = useState(link.then_text);
  const [because, setBecause] = useState(link.because_text);
  const [conditions, setConditions] = useState(link.conditions.join("\n"));
  return (
    <form
      aria-label={`Edit ${link.code ?? "connection"}`}
      onSubmit={(event) => {
        event.preventDefault();
        editor.run(
          {
            kind: "patchLink",
            linkId: link.link_id,
            body: {
              expected_revision: link.revision,
              title: title.trim() || null,
              if_text: ifText.trim(),
              for_text: forText.trim(),
              then_text: thenText.trim(),
              because_text: because.trim(),
              conditions: conditions
                .split("\n")
                .map((line) => line.trim())
                .filter(Boolean),
            },
          },
          `Edited ${link.code ?? "a connection"}`,
          onDone,
        );
      }}
    >
      <p className="text-meta text-grey">Editing connection {link.code}</p>
      <Field label="Title">
        <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} className={INPUT} />
      </Field>
      <Field label="If">
        <textarea value={ifText} onChange={(event) => setIf(event.target.value)} rows={2} className={INPUT} />
      </Field>
      <Field label="For">
        <input value={forText} onChange={(event) => setFor(event.target.value)} className={INPUT} />
      </Field>
      <Field label="Then">
        <textarea value={thenText} onChange={(event) => setThen(event.target.value)} rows={2} className={INPUT} />
      </Field>
      <Field label="Because">
        <textarea value={because} onChange={(event) => setBecause(event.target.value)} rows={2} className={INPUT} />
      </Field>
      <Field label="Conditions (one per line)">
        <textarea value={conditions} onChange={(event) => setConditions(event.target.value)} rows={3} className={INPUT} />
      </Field>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" disabled={editor.busy}>
          Save
        </Button>
        <Button type="button" variant="secondary" size="sm" onClick={onDone}>
          Cancel
        </Button>
        <span className="flex-1" />
        <DeleteButton
          label="Delete connection"
          confirm="Its evidence goes with it; Undo brings both back."
          busy={editor.busy}
          onDelete={() => editor.run({ kind: "deleteLink", linkId: link.link_id, revision: link.revision }, `Deleted ${link.code ?? "a connection"}`, onDone)}
        />
      </div>
    </form>
  );
}

/** "Needs evidence" with Find evidence, for connections no check has judged (C41, C40). */
export function NeedsEvidence({ links, graph, editor }: { links: TocLink[]; graph: TocGraph; editor: Editor | null }) {
  const running = graph.check_status === "drafting" || graph.check_status === "checking";
  const unchecked = links.filter((link) => link.state === "unchecked");
  if (unchecked.length === 0) return null;
  return (
    <div className="mt-3 border-l-[3px] border-blue bg-blue-tint-2 px-3 py-2.5">
      <p className="text-body font-bold text-ink">Needs evidence</p>
      <p className="text-body">No check has looked for evidence on {unchecked.length === 1 ? "this connection" : `${unchecked.length} of its connections`} yet.</p>
      {editor !== null && (
        <div className="mt-2">
          <Button
            size="sm"
            disabled={editor.busy || running}
            onClick={() => editor.run({ kind: "check", body: { link_ids: unchecked.map((link) => link.link_id), mode: "new_items" } })}
          >
            {running ? "A check is running" : "Find evidence"}
          </Button>
        </div>
      )}
    </div>
  );
}
