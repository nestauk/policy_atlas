import { useParams } from "react-router";

import { useFindings } from "../api/queries";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { Card } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";

/** Findings: the extracted findings with their run-scoped relevance marks —
 * `priority` annotates post-vetting survivors, it never dials the vetter. */
export function FindingsView() {
  const { projectId = "" } = useParams();
  const findings = useFindings(projectId, { page_size: 200 });

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <h1 className="mb-5 font-display text-xl font-extrabold text-navy">Findings</h1>

      {findings.isPending && (
        <div aria-busy="true" aria-label="Loading findings" className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {findings.isError &&
        (errorCode(findings.error) === "unauthenticated" ? (
          <ReauthRedirect />
        ) : (
          <Card role="alert" className="p-8 text-center text-[13px] text-navy">
            Findings couldn't be loaded.{" "}
            <button
              type="button"
              className="cursor-pointer font-bold text-blue hover:underline"
              onClick={() => void findings.refetch()}
            >
              Retry
            </button>
          </Card>
        ))}

      {findings.data !== undefined && findings.data.data.length === 0 && (
        <Card role="status" className="p-8 text-center text-[13px] text-grey">
          No findings yet — they appear once the analysis reads sources in full.
        </Card>
      )}

      {findings.data !== undefined && findings.data.data.length > 0 && (
        <ul role="list" className="space-y-2">
          {findings.data.data.map((finding) => (
            <li key={finding.finding_id}>
              <Card className="px-4 py-3">
                <p className="text-[13px] leading-relaxed text-ink">
                  {scrub(finding.statement)}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {finding.relevance === "priority" && <Chip tone="blue">Priority</Chip>}
                  {finding.profile !== null && finding.profile !== undefined && (
                    <Chip tone="soft">{scrub(finding.profile)}</Chip>
                  )}
                  <span className="text-[11.5px] text-grey">
                    {scrub(finding.source_title)}
                  </span>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
