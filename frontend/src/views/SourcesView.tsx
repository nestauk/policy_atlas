import { useParams, useSearchParams } from "react-router";

import { useEvidence } from "../api/queries";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { Button } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";

const STATUS_TONE: Record<string, "default" | "blue" | "soft" | "green" | "yellow" | "red"> = {
  found: "soft",
  screened_out: "soft",
  relevant: "blue",
  not_selected: "soft",
  selected: "blue",
  read_in_full: "blue",
  findings_extracted: "green",
  cited: "green",
  unavailable: "yellow",
};

const STATUS_FILTERS = ["all", "relevant", "screened_out", "cited", "unavailable"] as const;

/** Sources: the evidence list with its honest status ladder. Filters live in
 * the URL (?status=…) — shareable and refresh-safe. */
export function SourcesView() {
  const { projectId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = searchParams.get("status") ?? "all";
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;
  const evidence = useEvidence(projectId, { page, page_size: 50 });

  // ponytail: filtering is client-side over one server page — the pager
  // below shows unfiltered totals for that reason. The honest upgrade
  // path is a server-side `?status=` filter (with pagination totals that
  // reflect it), once the read model supports it.
  const isFiltered = statusFilter !== "all";
  const rows =
    evidence.data?.data.filter(
      (item) => statusFilter === "all" || item.status === statusFilter,
    ) ?? [];

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-xl font-extrabold text-navy">Sources</h1>
        <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-1.5">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter}
              type="button"
              aria-pressed={statusFilter === filter}
              onClick={() => {
                setSearchParams((current) => {
                  const next = new URLSearchParams(current);
                  if (filter === "all") next.delete("status");
                  else next.set("status", filter);
                  next.delete("page");
                  return next;
                });
              }}
              className={`cursor-pointer border px-2.5 py-1 text-[11.5px] font-semibold focus-visible:outline-2 focus-visible:outline-blue ${
                statusFilter === filter
                  ? "border-blue bg-blue-tint text-blue"
                  : "border-line-2 bg-paper text-grey hover:text-navy"
              }`}
            >
              {filter === "all" ? "All" : filter.replaceAll("_", " ")}
            </button>
          ))}
        </div>
      </header>

      {evidence.isPending && (
        <div aria-busy="true" aria-label="Loading sources" className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {evidence.isError &&
        (errorCode(evidence.error) === "unauthenticated" ? (
          <ReauthRedirect />
        ) : (
          <Card role="alert" className="p-8 text-center text-[13px] text-navy">
            Sources couldn't be loaded.{" "}
            <button
              type="button"
              className="cursor-pointer font-bold text-blue hover:underline"
              onClick={() => void evidence.refetch()}
            >
              Retry
            </button>
          </Card>
        ))}

      {evidence.data !== undefined && rows.length === 0 && (
        <Card role="status" className="p-8 text-center text-[13px] text-grey">
          {statusFilter === "all"
            ? "No sources yet — they arrive as the analysis searches."
            : "No sources match this filter."}
        </Card>
      )}

      {rows.length > 0 && (
        <ul role="list" className="space-y-2">
          {rows.map((item, index) => (
            <li key={`${item.source_id}-${index}`}>
              <Card className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-semibold text-navy">
                    {scrub(item.title)}
                  </p>
                  <p className="mt-0.5 text-[11.5px] text-grey">
                    {[item.year, item.venue, item.origin]
                      .filter((value) => value !== null && value !== undefined)
                      .map((value) => scrub(String(value)))
                      .join(" · ")}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Chip tone={STATUS_TONE[item.status] ?? "default"}>
                    {item.status.replaceAll("_", " ")}
                  </Chip>
                  {item.appraisal_tier !== null && item.appraisal_tier !== undefined && (
                    <Chip tone="soft">{scrub(item.appraisal_tier)}</Chip>
                  )}
                  {item.cited && <Chip tone="green">Cited</Chip>}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {evidence.data !== undefined &&
        evidence.data.pagination.total_items > evidence.data.pagination.page_size && (
          <nav aria-label="Pages" className="mt-5 flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1}
              onClick={() =>
                setSearchParams((current) => {
                  const next = new URLSearchParams(current);
                  next.set("page", String(page - 1));
                  return next;
                })
              }
            >
              Previous
            </Button>
            <span className="text-xs text-grey">
              {isFiltered
                ? "Filtered within this page"
                : `Page ${page} of ${Math.ceil(
                    evidence.data.pagination.total_items / evidence.data.pagination.page_size,
                  )}`}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={
                page >=
                Math.ceil(
                  evidence.data.pagination.total_items / evidence.data.pagination.page_size,
                )
              }
              onClick={() =>
                setSearchParams((current) => {
                  const next = new URLSearchParams(current);
                  next.set("page", String(page + 1));
                  return next;
                })
              }
            >
              Next
            </Button>
          </nav>
        )}
    </main>
  );
}
