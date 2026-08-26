import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router";

import type { components } from "../api/gen/types";
import { useApiClient, useFindings, useGroups, useProject } from "../api/queries";
import { HighlightedContext } from "./ArtefactView";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { Card } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { Tooltip } from "../ui/radix/Tooltip";
import {
  CAUSALITY_LABEL,
  CLAIM_BASIS_LABEL,
  CLAIM_LEVEL_LABEL,
  CONTEXT_LEVEL_LABEL,
  CONTEXT_TYPE_LABEL,
  DIRECTION_LABEL,
  DIRECTION_TONE,
  EFFECT_BASIS_LABEL,
  ESTIMATE_LEVEL_LABEL,
  findingLabel,
  PROFILE_LABEL,
} from "./findingsVocabulary";
import { FILTER_CHIP_CLASS, TABLE_HEADER_TEXT_CLASS } from "./sourcesPresentation";

type FindingOut = components["schemas"]["FindingOut"];
type IofFinding = Extract<FindingOut, { profile: "iof" }>;
type IcfFinding = Extract<FindingOut, { profile: "icf" }>;

/** The IOF expansion's statistics vocabulary — the as-built keys
 *  (`ci_lower`/`ci_upper`/`standard_error`/`i_squared`/`tau2`), never the
 *  demo's `ci`/`se`/`i2` (transcription trap 1). */
export function statRows(statistics: IofFinding["statistics"]): Array<[string, string]> {
  const rows: Array<[string, string]> = [];
  if (statistics.effect_size !== null && statistics.effect_size !== undefined) {
    const type = statistics.effect_size_type;
    rows.push([
      "Effect size",
      `${statistics.effect_size}${typeof type === "string" && type !== "" ? ` (${type})` : ""}`,
    ]);
  }
  if (
    statistics.ci_lower !== null &&
    statistics.ci_lower !== undefined &&
    statistics.ci_upper !== null &&
    statistics.ci_upper !== undefined
  ) {
    rows.push(["95% CI", `[${statistics.ci_lower}, ${statistics.ci_upper}]`]);
  }
  if (statistics.standard_error !== null && statistics.standard_error !== undefined) {
    rows.push(["SE", String(statistics.standard_error)]);
  }
  if (statistics.p_value !== null && statistics.p_value !== undefined) {
    rows.push(["p", String(statistics.p_value)]);
  }
  if (statistics.n !== null && statistics.n !== undefined) rows.push(["N", String(statistics.n)]);
  if (statistics.k !== null && statistics.k !== undefined) {
    rows.push(["Studies (k)", String(statistics.k)]);
  }
  if (statistics.i_squared !== null && statistics.i_squared !== undefined) {
    rows.push(["I²", String(statistics.i_squared)]);
  }
  if (statistics.tau2 !== null && statistics.tau2 !== undefined) {
    rows.push(["τ²", String(statistics.tau2)]);
  }
  return rows;
}

function DefinitionRow({ label, value }: { label: string; value: string | null }) {
  if (value === null || value === "") return null;
  return (
    <div className="contents">
      <dt className="text-grey">{label}</dt>
      <dd className="font-medium text-navy">{scrub(value)}</dd>
    </div>
  );
}

/** The shared grounding shape: the finding's exact anchoring words. The
 *  verified tick renders only when verification actually passed. */
function ExactWords({
  projectId,
  finding,
}: {
  projectId: string;
  finding: FindingOut;
}) {
  const client = useApiClient();
  const chunkId = finding.chunk_id ?? null;
  const quote = finding.quote ?? "";
  const context = useQuery({
    queryKey: ["projects", projectId, "finding-chunk-context", chunkId, quote],
    enabled: chunkId !== null && quote !== "",
    retry: false,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/projects/{project_id}/chunks/{chunk_id}/context",
        {
          params: {
            path: { project_id: projectId, chunk_id: chunkId ?? "" },
            query: { quote },
          },
        },
      );
      if (data === undefined) throw error;
      return data;
    },
  });
  return (
    <div>
      <h3 className="mb-2 text-meta font-bold uppercase tracking-[0.06em] text-grey">
        The exact words
      </h3>
      {context.data?.context !== undefined && context.data.context !== "" ? (
        <p className="text-body leading-relaxed text-grey">
          <HighlightedContext text={context.data.context} quote={quote} />{" "}
          {finding.quote_verified === true && (
            <span className="not-italic text-green">✓ verified</span>
          )}
        </p>
      ) : typeof quote === "string" && quote !== "" ? (
        <p className="text-body italic leading-relaxed text-grey">
          “{scrub(quote)}”{" "}
          {finding.quote_verified === true && (
            <span className="not-italic text-green">✓ verified</span>
          )}
        </p>
      ) : (
        <p className="text-body text-grey">No anchoring quote recorded.</p>
      )}
    </div>
  );
}

function IofExpansion({ finding, projectId }: { finding: IofFinding; projectId: string }) {
  const stats = statRows(finding.statistics);
  const qualifiers = finding.stratum_qualifiers ?? [];
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div>
        <h3 className="mb-2 text-meta font-bold uppercase tracking-[0.06em] text-grey">
          Reported numbers
        </h3>
        {stats.length === 0 && finding.estimate_level === null ? (
          <p className="text-body text-grey">
            No numbers reported — recorded as direction only.
          </p>
        ) : (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-caption">
            {stats.map(([label, value]) => (
              <DefinitionRow key={label} label={label} value={value} />
            ))}
            <DefinitionRow label="Comparator" value={finding.comparator ?? null} />
            <DefinitionRow
              label="Estimate level"
              value={findingLabel(ESTIMATE_LEVEL_LABEL, finding.estimate_level)}
            />
            <DefinitionRow
              label="Causality by design"
              value={findingLabel(CAUSALITY_LABEL, finding.causality_by_design)}
            />
            <DefinitionRow
              label="Effect basis"
              value={findingLabel(EFFECT_BASIS_LABEL, finding.effect_basis)}
            />
            <DefinitionRow label="Geography" value={finding.study_geography ?? null} />
            <DefinitionRow label="Population" value={finding.population ?? null} />
            <DefinitionRow label="Setting" value={finding.setting ?? null} />
            <DefinitionRow label="Study design" value={finding.study_design ?? null} />
          </dl>
        )}
        <div className="mt-2 flex flex-wrap gap-1.5">
          {finding.is_primary === true && <Chip tone="blue">Primary outcome</Chip>}
          {qualifiers.map((qualifier, index) => (
            <Chip key={index} tone="soft">
              {Object.entries(qualifier)
                .map(([type, value]) => `${scrub(type)}: ${scrub(value)}`)
                .join(" · ")}
            </Chip>
          ))}
        </div>
      </div>
      <ExactWords projectId={projectId} finding={finding} />
    </div>
  );
}

function IcfExpansion({ finding, projectId }: { finding: IcfFinding; projectId: string }) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div>
        <h3 className="mb-2 text-meta font-bold uppercase tracking-[0.06em] text-grey">
          Context detail
        </h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-caption">
          <DefinitionRow
            label="Context type"
            value={findingLabel(CONTEXT_TYPE_LABEL, finding.context_type)}
          />
          <DefinitionRow label="Context" value={finding.context_label ?? null} />
          <DefinitionRow label="Level" value={findingLabel(CONTEXT_LEVEL_LABEL, finding.level)} />
          <DefinitionRow
            label="Claim level"
            value={findingLabel(CLAIM_LEVEL_LABEL, finding.claim_level)}
          />
          <DefinitionRow
            label="Claim basis"
            value={findingLabel(CLAIM_BASIS_LABEL, finding.claim_basis)}
          />
          <DefinitionRow label="Population" value={finding.population ?? null} />
          <DefinitionRow label="Setting" value={finding.setting ?? null} />
          <DefinitionRow label="Geography" value={finding.study_geography ?? null} />
          <DefinitionRow label="Study design" value={finding.study_design ?? null} />
          <DefinitionRow label="Resources needed" value={finding.resource_requirements ?? null} />
          <DefinitionRow label="Workforce needed" value={finding.workforce_requirements ?? null} />
        </dl>
      </div>
      <ExactWords projectId={projectId} finding={finding} />
    </div>
  );
}

/** The finding's intervention-facet group label, for the "Grouped as" cell. */
function groupLabel(finding: FindingOut): string | null {
  for (const [facet, label] of Object.entries(finding.groups ?? {})) {
    if (facet.toLowerCase().replace(/ type$/, "").trim() === "intervention") return label;
  }
  return null;
}

function FindingRow({
  finding,
  showKind,
  expanded,
  onToggle,
  projectId,
}: {
  finding: FindingOut;
  showKind: boolean;
  expanded: boolean;
  onToggle: () => void;
  projectId: string;
}) {
  const group = groupLabel(finding);
  const directionLabel =
    finding.profile === "iof" ? findingLabel(DIRECTION_LABEL, finding.effect_direction) : null;
  const contextLabel =
    finding.profile === "icf" ? findingLabel(CONTEXT_TYPE_LABEL, finding.context_type) : null;
  return (
    <>
      <tr className="border-b border-line align-top transition-colors hover:bg-blue-tint-2">
        <td className="w-8 px-3 py-3">
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} finding: ${scrub(finding.intervention)}`}
            onClick={onToggle}
            className="cursor-pointer text-caption text-grey focus-visible:outline-2 focus-visible:outline-blue"
          >
            <span aria-hidden="true">{expanded ? "▾" : "▸"}</span>
          </button>
        </td>
        {showKind && (
          <td className="px-3 py-3">
            {findingLabel(PROFILE_LABEL, finding.profile) !== null && (
              <Chip tone={finding.profile === "iof" ? "blue" : "soft"}>
                {findingLabel(PROFILE_LABEL, finding.profile)}
              </Chip>
            )}
          </td>
        )}
        <td className="max-w-[260px] px-3 py-3 text-body font-medium leading-snug text-navy">
          {scrub(finding.intervention)}
        </td>
        <td className="max-w-[240px] px-3 py-3 text-body leading-snug text-navy">
          {finding.profile === "iof" ? scrub(finding.outcome) : scrub(finding.claim)}
        </td>
        <td className="px-3 py-3">
          {finding.profile === "iof" && directionLabel !== null && (
            <Tooltip
              content={
                <span className="text-caption">
                  {[finding.population, finding.study_design]
                    .filter((value): value is string => typeof value === "string" && value !== "")
                    .map((value) => scrub(value))
                    .join(" · ") || "No detail reported"}
                </span>
              }
            >
              <span>
                <Chip tone={DIRECTION_TONE[finding.effect_direction] ?? "soft"}>
                  {directionLabel}
                </Chip>
              </span>
            </Tooltip>
          )}
          {finding.profile === "icf" && contextLabel !== null && (
            <Chip tone="soft">{contextLabel}</Chip>
          )}
        </td>
        <td className="px-3 py-3">
          {group !== null && <Chip tone="soft">{scrub(group)}</Chip>}
        </td>
        <td className="max-w-[220px] px-3 py-3 text-body leading-snug">
          <Link
            to={`/projects/${projectId}/sources/all?source=${encodeURIComponent(finding.source_id)}`}
            className="text-grey hover:text-blue hover:underline"
          >
            {scrub(finding.source_title)}
          </Link>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-line bg-paper-2">
          <td />
          <td colSpan={showKind ? 6 : 5} className="px-4 py-4">
            {finding.profile === "iof" ? (
              <IofExpansion finding={finding} projectId={projectId} />
            ) : (
              <IcfExpansion finding={finding} projectId={projectId} />
            )}
          </td>
        </tr>
      )}
    </>
  );
}

/**
 * Findings, both kinds (strand 6): a kind-aware table over the
 * `profile`-discriminated union — IOF rows carry intervention/outcome/
 * direction, ICF rows the context claim; both expand to their full field
 * set and the shared "exact words" grounding panel. Kind and facet filters
 * are server-side and URL-addressable (`?profile=`, `?facet=` + `?group=`).
 */
export function FindingsView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  useDocumentTitle(project.data?.name, "Findings");
  const [searchParams, setSearchParams] = useSearchParams();
  const profileParam = searchParams.get("profile");
  const profile = profileParam === "iof" || profileParam === "icf" ? profileParam : undefined;
  const facet = searchParams.get("facet") ?? undefined;
  const group = searchParams.get("group") ?? undefined;
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;

  const findings = useFindings(projectId, {
    page,
    page_size: 50,
    profile,
    facet,
    group,
  });
  const groups = useGroups(projectId);
  const [open, setOpen] = useState<string | null>(null);

  const updateParams = (update: (next: URLSearchParams) => void) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      update(next);
      return next;
    });
  };

  const interventionFacet =
    groups.data?.facets?.find(
      (candidate) =>
        candidate.facet.toLowerCase().replace(/ type$/, "").trim() === "intervention",
    ) ?? null;

  const rows = findings.data?.data ?? [];
  const totalItems = findings.data?.pagination.total_items ?? 0;
  const showKind = profile === undefined;

  return (
    <main className="py-8">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Finding kind">
        {(
          [
            [undefined, "All kinds"],
            ["iof", PROFILE_LABEL.iof],
            ["icf", PROFILE_LABEL.icf],
          ] as const
        ).map(([value, label]) => (
          <button
            key={label}
            type="button"
            aria-pressed={profile === value}
            onClick={() =>
              updateParams((next) => {
                if (value === undefined) next.delete("profile");
                else next.set("profile", value);
                next.delete("page");
              })
            }
            className={`${FILTER_CHIP_CLASS} ${
              profile === value
                ? "border-blue bg-blue-tint text-blue"
                : "border-line bg-paper text-grey hover:bg-ground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {interventionFacet !== null && (interventionFacet.groups ?? []).length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Filter by group">
          <button
            type="button"
            aria-pressed={group === undefined}
            onClick={() =>
              updateParams((next) => {
                next.delete("facet");
                next.delete("group");
                next.delete("page");
              })
            }
            className={`${FILTER_CHIP_CLASS} ${
              group === undefined
                ? "border-blue bg-blue-tint text-blue"
                : "border-line bg-paper text-grey hover:bg-ground"
            }`}
          >
            All groups
          </button>
          {[...(interventionFacet.groups ?? [])]
            .sort((a, b) => (b.size ?? 0) - (a.size ?? 0))
            .slice(0, 8)
            .map((candidate) => (
              <button
                key={candidate.label}
                type="button"
                aria-pressed={group === candidate.label}
                onClick={() =>
                  updateParams((next) => {
                    if (group === candidate.label) {
                      next.delete("facet");
                      next.delete("group");
                    } else {
                      next.set("facet", interventionFacet.facet);
                      next.set("group", candidate.label);
                    }
                    next.delete("page");
                  })
                }
                className={`${FILTER_CHIP_CLASS} ${
                  group === candidate.label
                    ? "border-blue bg-blue-tint text-blue"
                    : "border-line bg-paper text-grey hover:bg-ground"
                }`}
              >
                {scrub(candidate.label)}
              </button>
            ))}
        </div>
      )}

      {findings.isPending && (
        <div aria-busy="true" aria-label="Loading findings" className="mt-5 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {findings.isError &&
        (errorCode(findings.error) === "unauthenticated" ? (
          <ReauthRedirect />
        ) : (
          <Card role="alert" className="mt-5 p-8 text-center text-body text-navy">
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

      {findings.data !== undefined && (
        <>
          <p className="mt-4 text-meta text-grey" role="status">
            {totalItems} finding{totalItems === 1 ? "" : "s"}
            {profile !== undefined || group !== undefined ? " match the filters" : ""}
          </p>
          <div className="mt-2 overflow-x-auto bg-paper shadow-sm ring-1 ring-line">
            <table className="w-full text-left">
              <thead className={`border-b border-line bg-paper-2 ${TABLE_HEADER_TEXT_CLASS}`}>
                <tr>
                  <th className="w-8 px-3 py-2.5">
                    <span className="sr-only">Expand</span>
                  </th>
                  {showKind && (
                    <th className="px-3 py-2.5">
                      Kind
                    </th>
                  )}
                  {["Intervention", "Outcome / claim", "Direction / context", "Grouped as", "Source"].map(
                    (heading) => (
                      <th
                        key={heading}
                        className="px-3 py-2.5"
                      >
                        {heading}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.map((finding) => (
                  <Fragment key={finding.finding_id}>
                    <FindingRow
                      finding={finding}
                      showKind={showKind}
                      expanded={open === finding.finding_id}
                      onToggle={() =>
                        setOpen(open === finding.finding_id ? null : finding.finding_id)
                      }
                      projectId={projectId}
                    />
                  </Fragment>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td
                      colSpan={showKind ? 7 : 6}
                      className="px-4 py-8 text-center text-body text-grey"
                    >
                      {profile !== undefined || group !== undefined
                        ? "No findings match these filters."
                        : "Findings appear here when an analysis runs at the deep setting — every finding extracted into a browsable database."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {findings.data.pagination.total_items > findings.data.pagination.page_size && (
            <nav aria-label="Pages" className="mt-5 flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() =>
                  updateParams((next) => next.set("page", String(page - 1)))
                }
                className="cursor-pointer border border-line-2 px-3 py-2 text-caption font-semibold text-navy disabled:cursor-default disabled:text-line-2"
              >
                Previous
              </button>
              <span className="text-caption text-grey">
                Page {page} of{" "}
                {Math.ceil(
                  findings.data.pagination.total_items / findings.data.pagination.page_size,
                )}
              </span>
              <button
                type="button"
                disabled={
                  page >=
                  Math.ceil(
                    findings.data.pagination.total_items / findings.data.pagination.page_size,
                  )
                }
                onClick={() =>
                  updateParams((next) => next.set("page", String(page + 1)))
                }
                className="cursor-pointer border border-line-2 px-3 py-2 text-caption font-semibold text-navy disabled:cursor-default disabled:text-line-2"
              >
                Next
              </button>
            </nav>
          )}
        </>
      )}
    </main>
  );
}
