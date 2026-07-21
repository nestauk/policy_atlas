import { useParams } from "react-router";

import { useDecisions } from "../api/queries";
import { scrub } from "../lib/scrub";
import { Card } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";

const KIND_TONE: Record<string, "default" | "blue" | "soft" | "green" | "yellow" | "red"> = {
  "steering.decision": "blue",
  "steering.pause": "yellow",
  "search.executed": "soft",
  "project.renamed": "soft",
  "project.archived": "soft",
  "plan.approved": "green",
};

/** Decision log: the user-facing audit trail — steering history plus the
 * allowlisted durable events, newest last, times shown honestly. */
export function DecisionsView() {
  const { projectId = "" } = useParams();
  const decisions = useDecisions(projectId, { page_size: 200 });

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <h1 className="mb-5 font-display text-xl font-extrabold text-navy">Decision log</h1>

      {decisions.isPending && (
        <div aria-busy="true" aria-label="Loading the decision log" className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {decisions.data !== undefined && decisions.data.data.length === 0 && (
        <Card role="status" className="p-8 text-center text-[13px] text-grey">
          Nothing decided yet — planning turns, steers and run events land here.
        </Card>
      )}

      {decisions.data !== undefined && decisions.data.data.length > 0 && (
        <ol className="space-y-1.5">
          {decisions.data.data.map((entry) => (
            <li key={entry.sequence}>
              <Card className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2.5">
                <time
                  dateTime={entry.occurred_at}
                  className="text-[11px] tabular-nums text-grey"
                >
                  {new Date(entry.occurred_at).toLocaleString()}
                </time>
                <Chip tone={KIND_TONE[entry.kind] ?? "default"}>{entry.kind}</Chip>
                <span className="min-w-0 flex-1 text-[12.5px] text-ink">
                  {scrub(entry.summary)}
                </span>
                {entry.decided_by !== null && entry.decided_by !== undefined && (
                  <span className="text-[11px] text-grey">by {entry.decided_by}</span>
                )}
              </Card>
            </li>
          ))}
        </ol>
      )}
    </main>
  );
}
