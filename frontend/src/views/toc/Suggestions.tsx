import { useState } from "react";

import type { components } from "../../api/gen/types";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import type { Editor } from "./Editing";

type Proposal = components["schemas"]["TocProposalOut"];

const SECTION_LABEL: Record<string, string> = {
  summary: "Summary",
  how_change_happens: "How change happens",
  assumptions: "Assumptions and evidence",
  tests: "What to test and measure",
  references: "References",
};

/**
 * Suggestions from the review after edits and from the chat (C45, C46): each
 * edit with its reason, Accept or Reject; the report sections that no longer
 * match, with Update the report. Nothing changes until the user accepts.
 */
export function Suggestions({ proposals, editor }: { proposals: Proposal[]; editor: Editor }) {
  const [problems, setProblems] = useState<string[]>([]);
  if (proposals.length === 0) return null;
  const decide = (proposalId: string, index: number | null, accept: boolean) =>
    editor.run({ kind: "proposal", proposalId, body: { index, accept } }, accept ? "Applied a suggestion" : undefined, (data) =>
      setProblems((data as { problems?: string[] } | undefined)?.problems ?? []),
    );
  return (
    <section id="toc-suggestions" aria-label="Suggestions" className="mb-3 grid gap-3">
      {proposals.map((proposal) => {
        const pending = proposal.edits.filter((edit) => edit.status === "pending");
        return (
          <div key={proposal.proposal_id} className="border border-line-2 bg-paper px-4 py-3">
            <p className="text-meta font-bold uppercase tracking-[0.06em] text-blue">
              {proposal.source === "review" ? "Review of your changes" : "Suggested in the chat"}
            </p>
            <p className="mt-1 text-body text-ink">{scrub(proposal.summary)}</p>
            {proposal.edits.length > 0 && (
              <ul className="mt-2">
                {proposal.edits.map((edit) => (
                  <li key={edit.index} className="grid grid-cols-[1fr_auto] items-start gap-3 border-t border-line py-2">
                    <div>
                      <p className="text-body font-semibold text-ink">{scrub(edit.line)}</p>
                      <p className="text-meta text-grey">{scrub(edit.reason)}</p>
                    </div>
                    {edit.status === "pending" ? (
                      <span className="flex gap-2">
                        <Button size="sm" variant="secondary" disabled={editor.busy} onClick={() => decide(proposal.proposal_id, edit.index, true)}>
                          Accept
                        </Button>
                        <Button size="sm" variant="secondary" disabled={editor.busy} onClick={() => decide(proposal.proposal_id, edit.index, false)}>
                          Reject
                        </Button>
                      </span>
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
                <ul className="mt-1 list-disc pl-5 text-body">
                  {proposal.report_findings.map((finding) => (
                    <li key={finding.section}>
                      <b>{SECTION_LABEL[finding.section] ?? finding.section}</b>: {scrub(finding.why)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {problems.length > 0 && (
              <ul role="alert" className="mt-2 text-body text-[var(--color-verdict-against-text)]">
                {problems.map((problem) => (
                  <li key={problem}>{scrub(problem)}</li>
                ))}
              </ul>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {pending.length > 1 && (
                <Button size="sm" disabled={editor.busy} onClick={() => decide(proposal.proposal_id, null, true)}>
                  Accept all
                </Button>
              )}
              {proposal.report_findings.length > 0 && (
                <Button size="sm" variant={pending.length > 1 ? "secondary" : "primary"} disabled={editor.busy} onClick={() => editor.run({ kind: "updateReport", proposalId: proposal.proposal_id })}>
                  Update the report
                </Button>
              )}
              <Button size="sm" variant="secondary" disabled={editor.busy} onClick={() => editor.run({ kind: "dismiss", proposalId: proposal.proposal_id })}>
                Dismiss
              </Button>
            </div>
          </div>
        );
      })}
    </section>
  );
}
