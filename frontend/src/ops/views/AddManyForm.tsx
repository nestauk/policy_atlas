import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useBlocker, useNavigate } from "react-router";

import { Figures } from "../../lib/figures";
import { formatCount } from "../../lib/format";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { LINK_CLASS } from "../../ui/brand/inlineActions";
import {
  OpsApiError,
  unwrap,
  useOpsClient,
  useOrganisations,
  useRefreshOps,
  type ImportProblem,
  type ImportRow,
} from "../api";
import { facts, orgInRefusal, plural, sentence } from "../format";
import {
  CHOOSE_ORGANISATION,
  CohortsField,
  FailedLine,
  Field,
  FORM_CARD_CLASS,
  OrganisationSelect,
  TABLE_WRAP_CLASS,
  TD_CLASS,
  TH_CLASS,
} from "../ui";

/** What happened to one person of the file. */
type Outcome =
  | { kind: "invited" | "added" }
  | { kind: "elsewhere"; org: string | null }
  | { kind: "refused"; message: string }
  | { kind: "deactivated" }
  | { kind: "failed"; status: number };

/** The file check: not run, running, could not run, or its answer. */
type Check = "idle" | "checking" | "failed" | { rows: ImportRow[]; errors: ImportProblem[] };

const EXAMPLE_CSV = 'email,name\nana.lopez@dhsc.example,Ana Lopez\nsam.lee@dhsc.example,"Lee, Sam"\n';
const EXAMPLE_HREF = `data:text/csv;charset=utf-8,${encodeURIComponent(EXAMPLE_CSV)}`;
const PREVIEW_ROWS = 10;
/** The question before an in-app move away from a running file. */
const LEAVE_WHILE_RUNNING = "People are still being added. If you leave now, the rest are not added. Leave this page?";

/** Sort one call's answer or failure into its outcome. Only `failed` is tried again. */
function outcomeOf(error: unknown): Outcome {
  if (!(error instanceof OpsApiError) || error.status === 0 || error.status >= 500) {
    return { kind: "failed", status: error instanceof OpsApiError ? error.status : 0 };
  }
  if (error.code === "enrolled_elsewhere") return { kind: "elsewhere", org: orgInRefusal(error.message) };
  if (error.code === "deactivated") return { kind: "deactivated" };
  return { kind: "refused", message: error.message === "" ? "The address was refused." : sentence(error.message) };
}

/** Why a person was not added, in the table's words. */
function reason(outcome: Outcome): string {
  if (outcome.kind === "elsewhere") {
    return outcome.org === null
      ? "Already in another organisation. Not tried again."
      : `Already in another organisation (${outcome.org}). Not tried again.`;
  }
  if (outcome.kind === "refused") return outcome.message;
  if (outcome.kind === "deactivated") return "Deactivated. To turn this person back on, add them with One person.";
  if (outcome.kind === "failed" && outcome.status === 0) return "No answer from the server. You can try again.";
  return "The server had an error. You can try again.";
}

/**
 * Many people from a CSV file: the server checks the whole file, then the
 * page creates each person in file order through the one-person route, so
 * each keeps its own audit row and outcome. The file lives in this
 * component's state only. A file run never turns a deactivated person back on.
 *
 * Args:
 *   onRunningChange: Told when a run starts and ends, so the page can lock
 *     what would leave it.
 */
export function AddManyForm({ onRunningChange }: { onRunningChange?: (running: boolean) => void }) {
  const navigate = useNavigate();
  const client = useOpsClient();
  const refresh = useRefreshOps();
  const organisations = useOrganisations();
  const [file, setFile] = useState<File | null>(null);
  const [check, setCheck] = useState<Check>("idle");
  const [orgId, setOrgId] = useState("");
  const [orgMissing, setOrgMissing] = useState(false);
  const [cohortIds, setCohortIds] = useState<string[]>([]);
  // The organisation and cohorts of the run, kept for Try again.
  const [runWith, setRunWith] = useState<{ orgId: string; cohortIds: string[] } | null>(null);
  const [outcomes, setOutcomes] = useState<Record<number, Outcome>>({});
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const running = progress !== null;
  // Only the latest file's check may answer; an older one that answers late is dropped.
  const latestCheck = useRef(0);
  // Set when the form goes away: a run stops before its next person.
  const left = useRef(false);
  const doneLine = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    left.current = false;
    return () => {
      left.current = true;
    };
  }, []);

  useEffect(() => onRunningChange?.(running), [running, onRunningChange]);

  useEffect(() => {
    if (!running) return;
    const ask = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", ask);
    return () => window.removeEventListener("beforeunload", ask);
  }, [running]);

  const blocker = useBlocker(running);
  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm(LEAVE_WHILE_RUNNING)) blocker.proceed();
    else blocker.reset();
  }, [blocker]);

  const runCheck = async (chosen: File) => {
    const mine = ++latestCheck.current;
    setCheck("checking");
    setOutcomes({});
    setRunWith(null);
    let next: Check;
    try {
      const csv = await chosen.text();
      next = await unwrap(client.POST("/api/v1/ops/people/import-check", { body: { csv } }));
    } catch {
      next = "failed";
    }
    if (mine === latestCheck.current) setCheck(next);
  };

  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0] ?? null;
    setFile(chosen);
    if (chosen === null) setCheck("idle");
    else void runCheck(chosen);
  };

  const run = async (people: readonly ImportRow[], settings: { orgId: string; cohortIds: string[] }) => {
    setRunWith(settings);
    setProgress({ done: 0, total: people.length });
    for (const [index, row] of people.entries()) {
      if (left.current) return;
      let outcome: Outcome;
      try {
        const created = await unwrap(
          client.POST("/api/v1/ops/people", {
            body: {
              email: row.email,
              display_name: row.display_name,
              org_id: settings.orgId,
              cohort_ids: settings.cohortIds,
              reactivate: false,
            },
          }),
        );
        outcome = { kind: created.invitation_sent ? "invited" : "added" };
      } catch (error) {
        outcome = outcomeOf(error);
      }
      setOutcomes((current) => ({ ...current, [row.line]: outcome }));
      setProgress({ done: index + 1, total: people.length });
    }
    setProgress(null);
    void refresh();
  };

  const result = typeof check === "object" ? check : null;
  const rows = result?.rows ?? [];
  const ready = result !== null && result.errors.length === 0 && rows.length > 0;
  const finished = !running && runWith !== null;
  // From the first Create until the person leaves, the file and its settings stay as run.
  const locked = runWith !== null;
  const outcomeList = rows.flatMap((row) => (outcomes[row.line] === undefined ? [] : [{ row, outcome: outcomes[row.line] }]));
  const count = (kind: Outcome["kind"]) => outcomeList.filter((entry) => entry.outcome.kind === kind).length;
  const notAdded = outcomeList.filter((entry) => entry.outcome.kind !== "invited" && entry.outcome.kind !== "added");
  const failed = notAdded.filter((entry) => entry.outcome.kind === "failed").map((entry) => entry.row);
  const orgName = organisations.data?.find((org) => org.org_id === orgId)?.name;

  useEffect(() => {
    if (finished) doneLine.current?.focus();
  }, [finished]);

  const create = () => {
    if (orgId === "") {
      setOrgMissing(true);
      document.getElementById("many-org")?.focus();
      return;
    }
    void run(rows, { orgId, cohortIds });
  };

  return (
    <div className={FORM_CARD_CLASS}>
      <Field
        id="many-file"
        label="File"
        help={
          <>
            A CSV file with a header line and two columns: email and name.{" "}
            <a href={EXAMPLE_HREF} download="people-example.csv" className={LINK_CLASS}>
              Download an example file
            </a>
          </>
        }
      >
        {(describedBy) => (
          <input
            id="many-file"
            type="file"
            accept=".csv,text/csv"
            disabled={locked || check === "checking"}
            aria-describedby={describedBy}
            // Choosing the same, corrected file again must check it again.
            onClick={(event) => {
              event.currentTarget.value = "";
            }}
            onChange={onFile}
            className={cn(
              "w-full min-w-0 text-body text-ink",
              "file:mr-3 file:h-10 file:cursor-pointer file:border file:border-line-2 file:bg-paper file:px-3.5",
              "file:text-meta file:font-semibold file:text-navy file:transition-colors file:duration-150 hover:file:bg-hover-fill",
              "disabled:text-grey disabled:file:cursor-default disabled:file:bg-ground disabled:file:text-grey disabled:hover:file:bg-ground",
            )}
          />
        )}
      </Field>
      <Field id="many-org" label="Organisation" error={orgMissing && orgId === "" ? CHOOSE_ORGANISATION : null}>
        {(describedBy) => (
          <OrganisationSelect
            id="many-org"
            label="Organisation"
            organisations={organisations.data ?? []}
            value={orgId}
            onChange={setOrgId}
            describedBy={describedBy}
            invalid={orgMissing && orgId === ""}
            disabled={locked}
          />
        )}
      </Field>
      <CohortsField
        id="many-cohorts"
        values={cohortIds}
        onChange={setCohortIds}
        help="Everyone in the file joins these cohorts."
        disabled={locked}
      />

      {check === "failed" && file !== null && (
        <FailedLine message="Could not check the file." onRetry={() => void runCheck(file)} />
      )}
      {result !== null && result.errors.length > 0 && (
        <div role="alert" className="border border-red-tint-edge bg-red-tint/40 p-4">
          <p className="text-body font-semibold text-red">
            This file has {plural(result.errors.length, "problem")}. Correct the file and choose it again.
          </p>
          <ul className="mt-2 flex flex-col gap-1 text-body text-ink">
            {result.errors.map((problem, index) => (
              <li key={index}>{problem.line == null ? problem.message : `Line ${problem.line}: ${problem.message}`}</li>
            ))}
          </ul>
        </div>
      )}
      {ready && !finished && !running && (
        <div className="flex flex-col gap-3">
          <p className="text-body font-semibold text-navy">
            {rows.length === 1 ? "1 person is" : `${formatCount(rows.length)} people are`} ready to add
            {orgName === undefined ? "" : ` to ${orgName}`}.
          </p>
          <PeopleTable rows={rows.slice(0, PREVIEW_ROWS).map((row) => ({ row }))} />
          {rows.length > PREVIEW_ROWS && (
            <p className="text-body text-grey">
              <Figures text={`and ${formatCount(rows.length - PREVIEW_ROWS)} more`} />
            </p>
          )}
        </div>
      )}

      {/* One live region, always there, holding the current line; empty, it
          gives back the card's gap so the form keeps its rhythm. */}
      <div role="status" className="flex flex-col gap-1 empty:-mt-6">
        {check === "checking" && <p className="text-body text-grey">Checking the file…</p>}
        {progress !== null && (
          <>
            {/* Read once as it appears, not again for every person. */}
            <p aria-live="off" className="text-body font-semibold text-navy">
              <Figures text={`Adding people: ${formatCount(progress.done)} of ${formatCount(progress.total)}.`} />
            </p>
            <p className="text-body text-grey">Keep this page open until it finishes.</p>
          </>
        )}
        {finished && (
          <p ref={doneLine} tabIndex={-1} className="text-body font-semibold text-navy focus-visible:outline-none">
            <Figures
              text={facts(
                `${formatCount(count("invited"))} invited`,
                `${formatCount(count("added"))} added, no email`,
                `${formatCount(count("elsewhere"))} already in another organisation`,
                ...(count("refused") > 0 ? [`${formatCount(count("refused"))} refused`] : []),
                ...(count("deactivated") > 0 ? [`${formatCount(count("deactivated"))} deactivated`] : []),
                `${formatCount(count("failed"))} failed`,
              )}
            />
          </p>
        )}
      </div>

      {finished && notAdded.length > 0 && (
        <div className="flex flex-col gap-3">
          <h2 className="text-body font-semibold text-navy">People who were not added</h2>
          <PeopleTable rows={notAdded.map((entry) => ({ row: entry.row, reason: reason(entry.outcome) }))} />
        </div>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3 pt-2 max-md:flex-col-reverse max-md:items-stretch">
        {finished ? (
          <>
            {failed.length > 0 && runWith !== null && (
              <Button variant="outline" onClick={() => void run(failed, runWith)}>
                Try again
              </Button>
            )}
            <Button onClick={() => navigate("/people")}>Done</Button>
          </>
        ) : (
          <>
            <Button variant="ghost" disabled={running} onClick={() => navigate("/people")}>
              Cancel
            </Button>
            <Button disabled={running || !ready} onClick={create}>
              {ready
                ? `Create ${plural(rows.length, "account")} and send invitations`
                : "Create accounts and send invitations"}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

/** The file's people: email and name, with the reason when they were not added. */
function PeopleTable({ rows }: { rows: ReadonlyArray<{ row: ImportRow; reason?: string }> }) {
  const withReason = rows.some((entry) => entry.reason !== undefined);
  return (
    // Fits the form's column: the cells wrap rather than scroll sideways.
    <div className={TABLE_WRAP_CLASS}>
      <table className="w-full table-fixed border-collapse text-left">
        <thead>
          <tr>
            <th className={cn(TH_CLASS, "pl-0", withReason ? "w-[44%]" : "w-[60%]")}>Email</th>
            <th className={cn(TH_CLASS, withReason ? "w-[20%]" : "w-[40%]")}>Name</th>
            {withReason && <th className={TH_CLASS}>Reason</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ row, reason: why }) => (
            <tr key={row.line}>
              <td className={cn(TD_CLASS, "break-words pl-0")}>{row.email}</td>
              <td className={cn(TD_CLASS, "break-words")}>{row.display_name}</td>
              {withReason && <td className={TD_CLASS}>{why}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
