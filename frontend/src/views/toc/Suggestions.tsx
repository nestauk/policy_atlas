import { useState } from "react";

import type { components } from "../../api/gen/types";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import type { Editor } from "./Editing";

type Proposal = components["schemas"]["TocProposalOut"];
type Edit = Proposal["edits"][number];

const SECTION_LABEL: Record<string, string> = {
  summary: "Summary",
  how_change_happens: "How change happens",
  assumptions: "Assumptions and evidence",
  tests: "What to test and measure",
  references: "References",
};

/** A route the canvas shows faded while its suggestion is hovered: its new boxes, links and pathway. */
export interface Preview {
  boxes: { key: string; layer: string; text: string }[];
  links: { key: string; source: string; dest: string }[];
  pathway: { kind: string; links: string[] } | null;
}

/** One route of a suggestion: its pending edits, offered together. */
interface Route {
  group: string;
  edits: Edit[];
  label: string;
  kind: string;
}

function routesOf(proposal: Proposal): Route[] {
  const groups = [...new Set(proposal.edits.flatMap((edit) => (edit.group != null && edit.status === "pending" ? [edit.group] : [])))];
  return groups.map((group) => {
    const edits = proposal.edits.filter((edit) => edit.group === group);
    const pathway = edits.find((edit) => edit.op === "add_pathway");
    return { group, edits, label: pathway?.label ?? "Suggested route", kind: pathway?.kind ?? "success" };
  });
}

/** The edits a route's preview draws: its own, and the pending ones it builds on from other routes. */
function previewOf(proposal: Proposal, route: Route): Preview {
  const pending = proposal.edits.filter((edit) => edit.status === "pending");
  const byKey = new Map(pending.filter((edit) => edit.key != null).map((edit) => [edit.key as string, edit]));
  const shown = new Set<Edit>(route.edits.filter((edit) => edit.status === "pending"));
  const todo = [...shown];
  while (todo.length > 0) {
    const edit = todo.pop() as Edit;
    for (const ref of [edit.source, edit.dest, ...(edit.links ?? [])]) {
      const needed = ref != null ? byKey.get(ref) : undefined;
      if (needed !== undefined && !shown.has(needed)) {
        shown.add(needed);
        todo.push(needed);
      }
    }
  }
  const list = [...shown];
  const pathway = list.find((edit) => edit.op === "add_pathway");
  return {
    boxes: list.filter((edit) => edit.op === "add_box").map((edit) => ({ key: edit.key ?? "", layer: edit.layer ?? "outcome_short", text: edit.text ?? "" })),
    links: list.filter((edit) => edit.op === "add_link").map((edit) => ({ key: edit.key ?? "", source: edit.source ?? "", dest: edit.dest ?? "" })),
    pathway: pathway !== undefined ? { kind: pathway.kind ?? "success", links: pathway.links ?? [] } : null,
  };
}

/** A suggestion's Accept and Reject: the outline button for the choice, the secondary beside it. */
function AcceptReject({ busy, onDecide }: { busy: boolean; onDecide: (accept: boolean) => void }) {
  return (
    <span className="mt-2 flex gap-2">
      <Button size="sm" variant="outline" disabled={busy} onClick={() => onDecide(true)}>
        Accept
      </Button>
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => onDecide(false)}>
        Reject
      </Button>
    </span>
  );
}

/** How many suggestions wait: one per route, or one per edit not offered as a route. */
export function pendingCount(proposals: Proposal[]): number {
  return proposals.reduce(
    (total, proposal) =>
      total + routesOf(proposal).length + proposal.edits.filter((edit) => edit.group == null && edit.status === "pending").length + (proposal.report_findings.length > 0 ? 1 : 0),
    0,
  );
}

/**
 * The suggestions, in the canvas's side panel (owner, 2026-11-04): a whole route
 * at a time where they come as routes (from the draft or the evidence), with
 * Accept or Reject; single edits from the review or the chat as before.
 * Hovering a route shows it faded on the canvas. Nothing changes until the
 * user accepts.
 */
export function Suggestions({
  proposals,
  editor,
  onPreview,
  checkNew,
}: {
  proposals: Proposal[];
  editor: Editor;
  onPreview: (preview: Preview | null) => void;
  /** Whether connections an accept adds get their evidence check at once (owner, 2026-11-05): not before the theory's first check. */
  checkNew: boolean;
}) {
  const [problems, setProblems] = useState<string[]>([]);
  const decide = (proposalId: string, body: { index: number | null; accept: boolean; group?: string }) => {
    onPreview(null);
    editor.run({ kind: "proposal", proposalId, body }, body.accept ? "Applied a suggestion" : undefined, (data) => {
      const decided = data as { problems?: string[]; new_link_ids?: string[] } | undefined;
      setProblems(decided?.problems ?? []);
      const added = decided?.new_link_ids ?? [];
      if (checkNew && added.length > 0) editor.run({ kind: "check", body: { link_ids: added, mode: "new_items" } });
    });
  };
  // A route, or a single suggested edit, shows on the canvas faded while hovered.
  const previewHandlers = (proposal: Proposal, route: Route) => ({
    onMouseEnter: () => onPreview(previewOf(proposal, route)),
    onMouseLeave: () => onPreview(null),
  });
  const hover = (proposal: Proposal, edit: Edit) =>
    edit.status === "pending" && ["add_box", "add_link", "add_pathway"].includes(edit.op) ? previewHandlers(proposal, { group: "", edits: [edit], label: "", kind: "" }) : {};
  return (
    <section id="toc-suggestions" aria-label="Suggestions" className="grid gap-4">
      <h3 className="text-body font-bold text-navy">Suggestions</h3>
      {proposals.length === 0 && <p className="text-body text-grey">No suggestions are waiting.</p>}
      {problems.length > 0 && (
        <ul role="alert" className="text-body text-red">
          {problems.map((problem) => (
            <li key={problem}>{scrub(problem)}</li>
          ))}
        </ul>
      )}
      {proposals.map((proposal) => {
        const routes = routesOf(proposal);
        const single = proposal.edits.filter((edit) => edit.group == null);
        const pendingSingle = single.filter((edit) => edit.status === "pending");
        return (
          <div key={proposal.proposal_id} className="border border-line-2 bg-paper px-4 py-3">
            <p className="text-body text-ink">{scrub(proposal.summary)}</p>
            {routes.length > 0 && (
              <ul className="mt-2">
                {routes.map((route) => {
                  const added = route.edits.filter((edit) => edit.op === "add_box" && edit.text != null).map((edit) => edit.text as string);
                  return (
                    <li
                      key={route.group}
                      className="border-t border-line py-2 hover:bg-blue-tint-2"
                      {...previewHandlers(proposal, route)}
                      onFocus={() => onPreview(previewOf(proposal, route))}
                      onBlur={() => onPreview(null)}
                    >
                      <p className="text-body font-semibold text-ink">{scrub(route.label)}</p>
                      <p className="text-meta text-grey">
                        {route.kind === "failure" ? "A way it could go wrong" : "A route to the goal"}
                        {added.length > 0 && <> · adds {added.map((text) => `“${scrub(text)}”`).join(", ")}</>}
                      </p>
                      <AcceptReject busy={editor.busy} onDecide={(accept) => decide(proposal.proposal_id, { index: null, accept, group: route.group })} />
                    </li>
                  );
                })}
              </ul>
            )}
            {single.length > 0 && (
              <ul className="mt-2">
                {single.map((edit) => (
                  <li key={edit.index} className="border-t border-line py-2 hover:bg-blue-tint-2" {...hover(proposal, edit)}>
                    <p className="text-body font-semibold text-ink">{scrub(edit.line)}</p>
                    <p className="text-meta text-grey">{scrub(edit.reason)}</p>
                    {edit.status === "pending" ? (
                      <AcceptReject busy={editor.busy} onDecide={(accept) => decide(proposal.proposal_id, { index: edit.index, accept })} />
                    ) : (
                      <span className="text-meta font-semibold text-grey">{edit.status === "accepted" ? "Accepted" : "Rejected"}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {proposal.report_findings.length > 0 && (
              <div className="mt-2 border-t border-line pt-2">
                <p className="text-body font-bold text-ink">The report no longer matches the theory in:</p>
                <ul className="mt-1 list-disc pl-5 text-body marker:text-grey">
                  {proposal.report_findings.map((finding) => (
                    <li key={finding.section}>
                      <span className="font-semibold">{SECTION_LABEL[finding.section] ?? finding.section}</span>: {scrub(finding.why)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {routes.length + pendingSingle.length > 1 && (
                <Button size="sm" variant="outline" disabled={editor.busy} onClick={() => decide(proposal.proposal_id, { index: null, accept: true })}>
                  Accept all
                </Button>
              )}
              {proposal.report_findings.length > 0 && (
                <Button size="sm" variant="secondary" disabled={editor.busy} onClick={() => editor.run({ kind: "updateReport", proposalId: proposal.proposal_id })}>
                  Update the report
                </Button>
              )}
              <Button size="sm" variant="ghost" disabled={editor.busy} onClick={() => editor.run({ kind: "dismiss", proposalId: proposal.proposal_id })}>
                Dismiss
              </Button>
            </div>
          </div>
        );
      })}
    </section>
  );
}
