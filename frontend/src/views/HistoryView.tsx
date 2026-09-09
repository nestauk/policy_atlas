import { useState } from "react";
import { useParams } from "react-router";

import { useDecisions, usePlanningTurns, useTask } from "../api/queries";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { LIFECYCLE_LABELS } from "../lib/vocabulary";
import { Card } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { mergeHistory } from "./historyPresentation";
import { LIFECYCLE_PAGE_CLASS } from "./listPageChrome";

const PAGE_SIZE = 200;

/**
 * History: the whole task, in the order it happened.
 *
 * The decision log started at plan approval, which left out the question that
 * began the work and the conversation that shaped the plan. Both are merged
 * in here, so they appear above the run events rather than nowhere.
 */
export function HistoryView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const decisions = useDecisions(taskId, { page_size: PAGE_SIZE });
  const turns = usePlanningTurns(taskId, { page_size: PAGE_SIZE });
  const [open, setOpen] = useState<string | null>(null);
  useDocumentTitle(task.data?.name, LIFECYCLE_LABELS.history);

  const isPending = decisions.isPending || turns.isPending;
  const isError = decisions.isError || turns.isError;
  const rows = mergeHistory(decisions.data?.data, turns.data?.data);

  if (isError && errorCode(decisions.error ?? turns.error) === "unauthenticated") {
    return <ReauthRedirect />;
  }

  return (
    <main className={`${LIFECYCLE_PAGE_CLASS} py-8`}>
      {isPending && (
        <div aria-busy="true" aria-label="Loading the history" className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-12 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {isError && (
        <Card role="alert" className="p-8 text-center text-body text-navy">
          The history couldn't be loaded.{" "}
          <button
            type="button"
            className="cursor-pointer font-bold text-blue hover:underline"
            onClick={() => {
              void decisions.refetch();
              void turns.refetch();
            }}
          >
            Retry
          </button>
        </Card>
      )}

      {!isPending && !isError && rows.length === 0 && (
        <Card role="status" className="p-8 text-center text-body text-grey">
          Nothing has happened yet — your question and everything after it will
          appear here.
        </Card>
      )}

      {rows.length > 0 && (
        <ol className="overflow-hidden border border-line-2 bg-paper">
          {rows.map((row) => {
            const expandable = (row.details ?? []).length > 0;
            const expanded = open === row.id;
            return (
              <li key={row.id} className="border-b border-line last:border-b-0">
                <button
                  type="button"
                  disabled={!expandable}
                  aria-expanded={expandable ? expanded : undefined}
                  onClick={() => {
                    if (expandable) setOpen(expanded ? null : row.id);
                  }}
                  className={`flex w-full items-baseline gap-3 px-4 py-3 text-left ${
                    expandable
                      ? "cursor-pointer hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-blue"
                      : "cursor-default"
                  }`}
                >
                  <time
                    dateTime={row.at}
                    className="w-32 shrink-0 text-body tabular-nums text-grey"
                  >
                    {new Date(row.at).toLocaleString()}
                  </time>
                  <Chip tone={row.tone}>{row.category}</Chip>
                  <span className="min-w-0 flex-1 text-body text-ink">{scrub(row.sentence)}</span>
                  {expandable && (
                    <span aria-hidden="true" className="text-body text-grey">
                      {expanded ? "▾" : "▸"}
                    </span>
                  )}
                </button>
                {expanded && (
                  <dl className="border-t border-line bg-paper-2 px-4 py-3">
                    {(row.details ?? []).map((detail) => (
                      <div key={detail.label}>
                        <dt className="text-meta font-bold uppercase tracking-[0.06em] text-grey">
                          {detail.label}
                        </dt>
                        <dd className="mt-1 whitespace-pre-wrap text-body text-navy">
                          {scrub(detail.value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </main>
  );
}
