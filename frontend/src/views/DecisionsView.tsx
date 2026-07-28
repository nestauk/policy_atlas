import { useState } from "react";
import { useParams } from "react-router";

import { useDecisions } from "../api/queries";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { Card } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { friendlyDecisionDetails, groupSearchDecisions } from "./decisionsPresentation";

const KIND_TONE: Record<string, "default" | "blue" | "soft" | "green" | "yellow" | "red"> = {
  "steering.decision": "blue",
  "steering.pause": "yellow",
  "search.executed.grouped": "soft",
  "project.renamed": "soft",
  "project.archived": "soft",
  "plan.approved": "green",
  "component.completed": "green",
  "component.failed": "red",
  "component.skipped": "yellow",
};

const KIND_LABELS: Record<string, string> = {
  "steering.decision": "Check-in",
  "steering.pause": "Check-in",
  "search.executed.grouped": "Search",
  "project.renamed": "Project",
  "project.archived": "Project",
  "plan.approved": "Plan",
  "component.completed": "Completed",
  "component.failed": "Failed",
  "component.skipped": "Skipped",
};

/** Decision log: friendly client-allowlisted detail and grouped search terms. */
export function DecisionsView() {
  const { projectId = "" } = useParams();
  const decisions = useDecisions(projectId, { page_size: 200 });
  const [open, setOpen] = useState<number | null>(null);
  const entries = decisions.data ? groupSearchDecisions(decisions.data.data) : [];

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <h1 className="font-display text-xl font-extrabold text-navy">Decision log</h1>
      <p className="mb-5 mt-1 text-[12.5px] text-grey">The project audit trail — check-ins, run decisions and recorded outcomes.</p>
      {decisions.isPending && <DecisionLoading />}
      {decisions.isError && (errorCode(decisions.error) === "unauthenticated" ? <ReauthRedirect /> : <Card role="alert" className="p-8 text-center text-[13px] text-navy">The decision log couldn't be loaded. <button type="button" className="cursor-pointer font-bold text-blue hover:underline" onClick={() => void decisions.refetch()}>Retry</button></Card>)}
      {decisions.data !== undefined && entries.length === 0 && <Card role="status" className="p-8 text-center text-[13px] text-grey">Nothing decided yet — planning turns, steers and run events land here.</Card>}
      {entries.length > 0 && <ol className="overflow-hidden border border-line-2 bg-paper">{entries.map((entry) => {
        const details = friendlyDecisionDetails(entry.detail);
        const expandable = details.length > 0;
        const expanded = open === entry.sequence;
        const checkIn = entry.kind === "steering.decision" || entry.kind === "steering.pause";
        return <li key={`${entry.kind}-${entry.sequence}`} className={`border-b border-line last:border-b-0 ${checkIn ? "border-l-2 border-l-yellow bg-yellow-tint" : ""}`}>
          <button type="button" disabled={!expandable} aria-expanded={expandable ? expanded : undefined} onClick={() => { if (expandable) setOpen(expanded ? null : entry.sequence); }} className={`flex w-full items-baseline gap-3 px-4 py-3 text-left ${expandable ? "cursor-pointer hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-blue" : "cursor-default"}`}>
            <time dateTime={entry.occurred_at} className="w-32 shrink-0 text-[11px] tabular-nums text-grey">{new Date(entry.occurred_at).toLocaleString()}</time>
            <Chip tone={KIND_TONE[entry.kind] ?? "default"}>{KIND_LABELS[entry.kind] ?? "Recorded"}</Chip>
            <span className="min-w-0 flex-1 text-[12.5px] text-ink">{scrub(entry.summary)}</span>
            {expandable && <span aria-hidden="true" className="text-[11px] text-grey">{expanded ? "▾" : "▸"}</span>}
          </button>
          {expanded && <dl className="grid grid-cols-1 gap-x-8 gap-y-1 border-t border-line bg-paper-2 px-4 py-3 sm:grid-cols-2">{details.map((detail) => <div key={detail.label} className="flex items-baseline justify-between gap-3 text-[12px]"><dt className="text-grey">{detail.label}</dt><dd className="text-right font-medium text-navy">{scrub(String(detail.value))}</dd></div>)}</dl>}
        </li>;
      })}</ol>}
    </main>
  );
}

function DecisionLoading() {
  return <div aria-busy="true" aria-label="Loading the decision log" className="space-y-2">{Array.from({ length: 6 }).map((_, index) => <div key={index} className="h-12 animate-pulse border border-line bg-paper-2" />)}</div>;
}
