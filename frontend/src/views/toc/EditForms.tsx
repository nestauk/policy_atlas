import { type FormEvent, useState } from "react";

import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { QUIET_CONTROL_CLASS } from "../../ui/brand/inlineActions";
import { CheckButton, type Editor, FIELD_CLASS, FIELD_LABEL_CLASS, LayerSelect } from "./Editing";
import type { BoxLayer, TocBox, TocGraph, TocLink } from "./types";

const INPUT = cn(FIELD_CLASS, "resize-y");

/** A submitted form's field, trimmed (a textarea submits CRLF line breaks; back to "\n"). */
function fieldOf(event: FormEvent<HTMLFormElement>): (name: string) => string {
  const data = new FormData(event.currentTarget);
  return (name) => String(data.get(name) ?? "").replace(/\r\n/g, "\n").trim();
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="mt-3 grid gap-1">
      <span className={FIELD_LABEL_CLASS}>{label}</span>
      {children}
    </label>
  );
}

/** Delete with a second press to confirm, naming what goes with it: the
 *  quiet control, then the archive confirm's form (the sentence, an outline
 *  "Delete" and a ghost "Keep"). Never red words: Undo brings it back. */
function DeleteButton({ label, confirm, onDelete, busy }: { label: string; confirm: string; onDelete: () => void; busy: boolean }) {
  const [asked, setAsked] = useState(false);
  return asked ? (
    <span role="group" aria-label={label} className="flex basis-full flex-wrap items-center gap-x-2 gap-y-1.5 border-t border-line pt-3">
      <span className="mr-auto text-body text-ink">{confirm}</span>
      <Button variant="outline" size="sm" disabled={busy} onClick={onDelete}>
        Delete
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setAsked(false)}>
        Keep
      </Button>
    </span>
  ) : (
    <button type="button" onClick={() => setAsked(true)} className={cn(QUIET_CONTROL_CLASS, "text-meta")}>
      {label}
    </button>
  );
}

/** Edit a box in place: every field, Save or Cancel, and Delete (C41). */
export function BoxEditForm({ box, graph, editor, onDone }: { box: TocBox; graph: TocGraph; editor: Editor; onDone: () => void }) {
  // The text stays controlled: the warning about its connections follows it as it is typed.
  const [text, setText] = useState(box.text);
  const [layer, setLayer] = useState<BoxLayer>(box.layer);
  const links = graph.links.filter((link) => link.source_box_id === box.box_id || link.target_box_id === box.box_id).length;
  return (
    <form
      aria-label={`Edit ${box.code ?? "box"}`}
      onSubmit={(event) => {
        event.preventDefault();
        const field = fieldOf(event);
        editor.run(
          {
            kind: "patchBox",
            boxId: box.box_id,
            body: {
              expected_revision: box.revision,
              text: text.trim(),
              layer,
              description: field("description") || null,
              criteria: { definition: field("definition") || null, indicator: field("indicator") || null, timing: field("timing") || null },
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
      <div className="mt-3 grid gap-1">
        <span aria-hidden="true" className={FIELD_LABEL_CLASS}>
          Layer
        </span>
        <LayerSelect value={layer} onChange={setLayer} className="w-full" />
      </div>
      <Field label="Description">
        <textarea name="description" defaultValue={box.description ?? ""} rows={3} maxLength={2000} className={INPUT} />
      </Field>
      <Field label="Definition">
        <input name="definition" defaultValue={box.result_criteria.definition ?? ""} className={FIELD_CLASS} />
      </Field>
      <Field label="Indicator">
        <input name="indicator" defaultValue={box.result_criteria.indicator ?? ""} className={FIELD_CLASS} />
      </Field>
      <Field label="Timing">
        <input name="timing" defaultValue={box.result_criteria.timing ?? ""} className={FIELD_CLASS} />
      </Field>
      {text.trim() !== box.text && links > 0 && (
        <p className="mt-2 text-body text-grey">Changing the text marks its {links === 1 ? "connection" : `${links} connections`} "evidence from the earlier wording".</p>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-3">
        <Button type="submit" variant="outline" size="sm" disabled={editor.busy || text.trim() === ""}>
          Save
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onDone}>
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
  return (
    <form
      aria-label={`Edit ${link.code ?? "connection"}`}
      onSubmit={(event) => {
        event.preventDefault();
        const field = fieldOf(event);
        editor.run(
          {
            kind: "patchLink",
            linkId: link.link_id,
            body: {
              expected_revision: link.revision,
              title: field("title") || null,
              if_text: field("if_text"),
              for_text: field("for_text"),
              then_text: field("then_text"),
              because_text: field("because_text"),
              conditions: field("conditions")
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
        <input name="title" defaultValue={link.title ?? ""} maxLength={200} className={FIELD_CLASS} />
      </Field>
      <Field label="If">
        <textarea name="if_text" defaultValue={link.if_text} rows={2} className={INPUT} />
      </Field>
      <Field label="For">
        <input name="for_text" defaultValue={link.for_text} className={FIELD_CLASS} />
      </Field>
      <Field label="Then">
        <textarea name="then_text" defaultValue={link.then_text} rows={2} className={INPUT} />
      </Field>
      <Field label="Because">
        <textarea name="because_text" defaultValue={link.because_text} rows={2} className={INPUT} />
      </Field>
      <Field label="Conditions (one per line)">
        <textarea name="conditions" defaultValue={link.conditions.join("\n")} rows={3} className={INPUT} />
      </Field>
      <div className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-3">
        <Button type="submit" variant="outline" size="sm" disabled={editor.busy}>
          Save
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onDone}>
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
  const unchecked = links.filter((link) => link.state === "unchecked");
  const ids = unchecked.map((link) => link.link_id);
  // Before the first check there is nothing to find evidence against (same gate as the canvas bar).
  if (unchecked.length === 0 || graph.check_status === "none") return null;
  return (
    <div className="mt-3 border-l-2 border-blue bg-blue-tint-2 px-3 py-2.5">
      <p className="text-body font-bold text-ink">Needs evidence</p>
      <p className="text-body">No check has looked for evidence on {unchecked.length === 1 ? "this connection" : `${unchecked.length} of its connections`} yet.</p>
      {editor !== null && (
        <div className="mt-2">
          <CheckButton graph={graph} editor={editor} ids={ids} mode="new_items" label="Find evidence" />
        </div>
      )}
    </div>
  );
}
