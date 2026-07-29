import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import type { components } from "../../../api/gen/types";
import { scrub } from "../../../lib/scrub";
import type { RunStreamState, StageEntry } from "../../../store/types";
import { Card, PaneHeading, StatusDot } from "../../../ui/brand/Card";
import { Chip } from "../../../ui/brand/Chip";
import {
  EvidenceDistributionChart,
  normaliseGeographies,
  orderThemes,
  PublicationYearsChart,
} from "../../../ui/charts/EvidenceDistributionChart";
import { CountUp } from "../../../ui/motion/CountUp";
import { Tooltip } from "../../../ui/radix/Tooltip";
import {
  ANALYSIS_DEPTH_LABEL,
  SEARCH_EFFORT_LABEL,
  SOURCES_LABEL,
  STEERING_MODE_LABEL,
  scopeChips,
  vocabLabel,
} from "../planVocabulary";
import { completionCopy, FUNNEL_STAGES, funnelBarWidth, screenedOutFooter, timelineSummary } from "./presentation";

type PlanDraft = components["schemas"]["PlanDraft"];
type Funnel = components["schemas"]["FunnelOut"];
type Coverage = components["schemas"]["CoverageOut"];
type Groups = components["schemas"]["GroupsOut"];
type Landscape = components["schemas"]["LandscapeOut"];

const BACKEND_LABELS: Record<string, string> = {
  openalex: "OpenAlex · academic research",
  overton: "Overton · policy documents",
};

function backendLabel(backend: string): string {
  return BACKEND_LABELS[backend] ?? scrub(backend);
}

function elapsed(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function stageTone(status: StageEntry["status"]): "running" | "complete" | "failed" | "idle" {
  if (status === "started") return "running";
  if (status === "completed") return "complete";
  if (status === "failed") return "failed";
  return "idle";
}

/** The right workspace pane during a run: durable read models augment (but
 * never replace) the stream's authoritative status, stages and check-ins. */
export function JourneyPane({
  projectId,
  stream,
  plan,
  funnel,
  coverage,
  groups,
  landscape,
  checkIn,
  terminal,
  onStartFreshRun,
}: {
  projectId: string;
  stream: RunStreamState;
  plan: PlanDraft | null;
  funnel?: Funnel;
  coverage?: Coverage;
  groups?: Groups;
  landscape?: Landscape;
  checkIn?: ReactNode;
  terminal?: ReactNode;
  onStartFreshRun?: () => void;
}) {
  const runStatus = stream.run?.status;
  const hasLandscape = Object.keys(landscape?.evidence_types ?? {}).length > 0 || Object.keys(landscape?.years ?? {}).length > 0 || Object.keys(landscape?.geographies ?? {}).length > 0 || (landscape?.themes?.length ?? 0) > 0;
  const hasGroups = (groups?.facets?.length ?? 0) > 0;
  const heading = runStatus === "succeeded" || runStatus === "degraded" ? "Analysis complete" : runStatus === "aborted" || runStatus === "failed" ? "Analysis stopped" : "Analysing the evidence…";

  return (
    <div className="h-full w-full min-w-0 max-w-full overflow-x-hidden overflow-y-auto px-5 py-5" style={{ scrollbarGutter: "stable" }}>
      {runStatus === "running" && <ProgressStrip stages={stream.stages} />}
      <PlanRecap plan={plan} />

      <nav aria-label="Journey sections" className="sticky top-0 z-20 -mx-5 mb-4 flex flex-wrap gap-x-3 gap-y-1 border-b border-line bg-ground/95 px-5 py-2 backdrop-blur-sm">
        <a className="shrink-0 text-[11px] font-bold uppercase tracking-wide text-navy hover:text-blue" href="#journey-timeline">Timeline</a>
        {funnel !== undefined && <a className="shrink-0 text-[11px] font-bold uppercase tracking-wide text-navy hover:text-blue" href="#journey-funnel">Funnel</a>}
        {coverage !== undefined && <a className="shrink-0 text-[11px] font-bold uppercase tracking-wide text-navy hover:text-blue" href="#journey-coverage">Coverage</a>}
        {hasGroups && <a className="shrink-0 text-[11px] font-bold uppercase tracking-wide text-navy hover:text-blue" href="#journey-groups">Groups</a>}
      </nav>

      <h2 className="mb-4 font-display text-[20px] font-semibold text-navy">{heading}</h2>
      <StatusBanner status={runStatus} />

      <div className="space-y-5">
        <CompletionCard projectId={projectId} status={runStatus} funnel={funnel} coverage={coverage} onStartFreshRun={onStartFreshRun} />
        {coverage !== undefined && <CoverageCard coverage={coverage} />}
        <section id="journey-timeline" className="scroll-mt-14">
          <Card className="anim-rise p-4">
            <PaneHeading className="mb-2 p-0">{runStatus === "succeeded" || runStatus === "degraded" || runStatus === "aborted" ? "How it got there" : "The plan in motion"}</PaneHeading>
            <Timeline stages={stream.stages} plan={plan} />
          </Card>
        </section>
        {checkIn}
        {funnel !== undefined && <FunnelCard funnel={funnel} />}
        {hasGroups && <GroupsCard groups={groups!} />}
        {hasLandscape && <LandscapeEmbed landscape={landscape!} />}
        {terminal}
      </div>
    </div>
  );
}

function StatusBanner({ status }: { status: string | undefined }) {
  if (status === "degraded") return <p className="mb-4 border-l-[3px] border-orange bg-yellow-tint p-3 text-[13px] text-navy">Completed with some flagged events — recorded in the decision log, not hidden.</p>;
  if (status === "aborted") return <p className="mb-4 border-l-[3px] border-orange bg-yellow-tint p-3 text-[13px] text-navy">You stopped this run. Everything completed so far is kept below.</p>;
  if (status === "failed") return <p className="mb-4 border-l-[3px] border-red bg-red-tint p-3 text-[13px] text-navy">This run failed. Whatever completed is kept and readable.</p>;
  return null;
}

function ProgressStrip({ stages }: { stages: StageEntry[] }) {
  if (stages.length === 0) return null;
  return <div className="mb-3 flex gap-1" aria-label="Run progress">{stages.map((stage, index) => <span key={`${stage.stage}-${index}`} className={`h-1 flex-1 ${stage.status === "completed" ? "bg-blue" : stage.status === "failed" || stage.status === "skipped" ? "bg-orange" : "anim-breathe bg-blue"}`} />)}</div>;
}

function PlanRecap({ plan }: { plan: PlanDraft | null }) {
  const [open, setOpen] = useState(false);
  if (plan === null || plan.question === null || plan.question === "") return null;
  const settings = [
    ["Search effort", vocabLabel(SEARCH_EFFORT_LABEL, plan.search_effort)],
    ["Analysis depth", vocabLabel(ANALYSIS_DEPTH_LABEL, plan.analysis_depth)],
    ["Sources", vocabLabel(SOURCES_LABEL, plan.backend_scope)],
    ["Check-ins", vocabLabel(STEERING_MODE_LABEL, plan.steering_mode)],
  ].filter((item): item is [string, string] => item[1] !== null);
  const constraints = scopeChips(plan.scope_constraints);
  return <Card className="mb-4 min-w-0">
    <button className="flex w-full min-w-0 items-baseline gap-3 px-4 py-3 text-left hover:bg-ground" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-label="Toggle plan recap">
      <PaneHeading className="shrink-0 p-0">The plan</PaneHeading>
      <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-navy">{scrub(plan.question)}</span>
      {plan.time_band !== null && plan.time_band !== "" && <Chip className="max-w-32 shrink truncate" tone="soft">{scrub(plan.time_band)}</Chip>}
      <span className="shrink-0 text-[11px] text-grey">{open ? "Hide" : "Details"}</span>
    </button>
    {open && <div className="anim-rise border-t border-line px-4 pb-4 pt-3">
      {settings.length > 0 && <div className="grid gap-px border border-line bg-line sm:grid-cols-2">{settings.map(([label, value]) => <div key={label} className="bg-paper px-3 py-2"><p className="text-[10px] font-bold uppercase tracking-wide text-grey">{label}</p><p className="text-[12px] font-medium text-navy">{value}</p></div>)}</div>}
      {(plan.scoping_notes ?? []).length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{plan.scoping_notes?.map((note) => <Chip key={note} tone="soft">{scrub(note)}</Chip>)}</div>}
      {constraints.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{constraints.map((chip) => <Chip key={chip} tone="blue">{scrub(chip)}</Chip>)}</div>}
      {(plan.screening_criteria ?? []).length > 0 && <div className="mt-3"><PaneHeading className="p-0">Screening criteria</PaneHeading><ul className="mt-1 space-y-1 text-[12px] text-navy">{plan.screening_criteria?.map((criterion) => <li key={criterion}>• {scrub(criterion)}</li>)}</ul></div>}
      {(plan.steps ?? []).length > 0 && <div className="mt-3"><PaneHeading className="p-0">Agreed steps</PaneHeading><ol className="mt-1 space-y-1 text-[12px] text-navy">{plan.steps?.map((step, index) => <li key={step.stage}>{index + 1}. {scrub(step.label)}{step.blurb !== "" && <span className="text-grey"> — {scrub(step.blurb)}</span>}</li>)}</ol></div>}
      {(plan.assumptions ?? []).length > 0 && <div className="mt-3"><PaneHeading className="p-0">Assumptions</PaneHeading><ul className="mt-1 space-y-1 text-[12px] text-grey">{plan.assumptions?.map((assumption) => <li key={assumption}>• {scrub(assumption)}</li>)}</ul></div>}
    </div>}
  </Card>;
}

type TimelineRow = {
  stage: string;
  label: string;
  status: StageEntry["status"] | "upcoming";
  blurb?: string;
  summary?: StageEntry["summary"];
  seconds?: number | null;
};

function Timeline({ stages, plan }: { stages: StageEntry[]; plan: PlanDraft | null }) {
  const rows = useMemo<TimelineRow[]>(() => {
    const seen = new Set(stages.map((entry) => entry.stage));
    // Plan steps that haven't emitted yet are UPCOMING — never "skipped".
    // "Skipped" is the server's word for a stage a prior failure took out;
    // rendering the future that way is a dishonest surface (live-check
    // finding, 2026-07-29).
    const upcoming = (plan?.steps ?? [])
      .filter((step) => !seen.has(step.stage))
      .map((step) => ({ stage: step.stage, label: step.label, status: "upcoming" as const, blurb: step.blurb, summary: undefined }));
    return [...stages, ...upcoming];
  }, [plan?.steps, stages]);
  if (rows.length === 0) return <p className="text-[12.5px] text-grey">Stages will appear as the analysis begins.</p>;
  return <ol aria-label="Stage timeline" className="space-y-2.5">{rows.map((entry, index) => {
    const reason = typeof entry.summary?.reason === "string" ? entry.summary.reason : null;
    const summary = timelineSummary(entry);
    const tooltip = <div className="space-y-1 text-[12px] text-navy"><p>{scrub(entry.blurb ?? entry.label)}</p>{entry.status === "completed" && typeof entry.seconds === "number" && <p className="text-grey">Took {elapsed(entry.seconds)}</p>}{reason !== null && <p className="text-red">{scrub(reason)}</p>}</div>;
    return <li key={`${entry.stage}-${index}`} className="flex min-w-0 items-start gap-2.5 text-[13px]"><StatusDot className="mt-1" tone={entry.status === "upcoming" ? "idle" : stageTone(entry.status)} /><div className="min-w-0 break-words"><Tooltip content={tooltip}><span className={`font-medium ${entry.status === "skipped" || entry.status === "upcoming" ? "text-grey" : "text-navy"}`}>{scrub(entry.label)}</span></Tooltip>{summary.length > 0 && <span className="ml-1.5 text-grey">— {summary.join(" · ")}</span>}{entry.status === "completed" && typeof entry.seconds === "number" && <span className="ml-1.5 text-grey">· {elapsed(entry.seconds)}</span>}{entry.status === "skipped" && <span className="ml-1.5 text-grey">skipped — a prior step failed</span>}{entry.status === "failed" && <span className="ml-1.5 text-red">stopped — recorded, carrying on</span>}{entry.status === "started" && entry.blurb !== undefined && entry.blurb !== "" && <p className="text-[12px] text-grey">{scrub(entry.blurb)}</p>}</div></li>;
  })}</ol>;
}

function FunnelCard({ funnel }: { funnel: Funnel }) {
  const max = typeof funnel.found === "number" ? funnel.found : 0;
  const rows = FUNNEL_STAGES.flatMap(([key, label, definition]) => {
    const value = funnel[key];
    return typeof value === "number" ? [{ key, label, definition, value }] : [];
  });
  if (rows.length === 0) return null;
  return <section id="journey-funnel" className="scroll-mt-14"><Card className="anim-rise p-4"><PaneHeading className="mb-3 p-0">From sources to evidence</PaneHeading><div className="space-y-2">{rows.map((row) => <Tooltip key={row.key} content={<p className="text-[12px] text-navy">{row.definition}</p>}><div className="flex items-center gap-3"><span className="w-28 shrink-0 text-right text-[11.5px] font-medium text-navy">{row.label}</span><span className="h-3 flex-1 bg-ground"><span className="anim-bar block h-full bg-blue" style={{ width: `${funnelBarWidth(row.value, max)}%` }} /></span><CountUp value={row.value} className="w-8 shrink-0 text-[12px] font-bold text-navy" /></div></Tooltip>)}</div>{typeof funnel.screened_out === "number" && <p className="mt-3 pl-[124px] text-[11.5px] text-grey">{screenedOutFooter(funnel.screened_out)}</p>}</Card></section>;
}

function CoverageCard({ coverage }: { coverage: Coverage }) {
  const details = coverage.backends_detail ?? [];
  return <section id="journey-coverage" className="scroll-mt-14"><Card className="anim-rise min-w-0 p-4"><PaneHeading className="mb-3 p-0">Where I looked</PaneHeading>{details.length > 0 ? <div className="grid min-w-0 gap-3 sm:grid-cols-2">{details.map((backend) => <div key={backend.backend} className="min-w-0 border border-line p-3"><div className="flex min-w-0 items-baseline justify-between gap-2"><span className="min-w-0 break-words text-[12px] font-bold text-navy">{backendLabel(backend.backend)}</span><span className="shrink-0 whitespace-nowrap text-[11px] text-grey"><CountUp value={backend.results} className="font-display text-[17px] font-bold text-blue" /> results · <CountUp value={backend.relevant} className="font-display text-[17px] font-bold text-blue" /> relevant</span></div><div className="mt-2 max-h-28 min-w-0 space-y-1 overflow-y-auto">{(backend.queries ?? []).map((query, index) => <div key={`${query.query}-${index}`} className="flex min-w-0 gap-2 text-[11px]"><span className="min-w-0 flex-1 truncate italic text-grey">“{scrub(query.query)}”</span><span className="shrink-0 text-navy">{query.results}</span></div>)}</div></div>)}</div> : <p className="break-words text-[12.5px] text-navy">{(coverage.backends ?? []).map(backendLabel).join(" · ")}</p>}<p className="mt-3 break-words text-[12.5px] text-navy">{scrub(coverage.sentence)}</p><p className="mt-1 text-[11px] text-grey">Relevant counts are attributed across this project; per-query relevance was not recorded.</p></Card></section>;
}

function CompletionCard({ projectId, status, funnel, coverage, onStartFreshRun }: { projectId: string; status: string | undefined; funnel?: Funnel; coverage?: Coverage; onStartFreshRun?: () => void }) {
  const copy = completionCopy(status);
  if (copy === null) return null;
  const counts = [typeof funnel?.relevant === "number" ? `${funnel.relevant} sources included` : null, typeof funnel?.cited === "number" ? `${funnel.cited} cited` : null].filter((count): count is string => count !== null);
  return <Card className={`anim-rise border-l-[3px] p-5 ${status === "degraded" ? "border-l-orange" : "border-l-green"}`}><PaneHeading className="mb-2 p-0">Done</PaneHeading><h3 className="font-display text-[18px] font-semibold text-navy">{copy.heading}</h3><p className="mt-1 text-[13px] text-navy">{counts.length > 0 ? `${counts.join(", ")} — ${copy.body}` : copy.body}</p>{coverage !== undefined && <p className="mt-2 text-[12px] text-grey">{scrub(coverage.sentence)}</p>}<div className="mt-4 flex flex-wrap gap-3"><Link className="cutout bg-blue px-3 py-2 text-[12px] font-bold text-white" to={`/projects/${projectId}/evidence-base`}>Read the evidence base</Link><Link className="border border-line-2 bg-paper px-3 py-2 text-[12px] font-bold text-navy" to={`/projects/${projectId}/sources`}>All sources</Link>{onStartFreshRun !== undefined && (
    // Replanning after a terminal run reaches `ready` in the thread; without
    // this control a replanned plan has no start affordance (the plan pane
    // only renders pre-first-run) — live-check finding, 2026-07-29.
    <button type="button" onClick={onStartFreshRun} className="cursor-pointer border border-line-2 bg-paper px-3 py-2 text-[12px] font-bold text-navy hover:bg-ground focus-visible:outline-2 focus-visible:outline-blue">Run the analysis again</button>
  )}</div></Card>;
}

function GroupsCard({ groups }: { groups: Groups }) {
  const facets = groups.facets ?? [];
  return <section id="journey-groups" className="scroll-mt-14"><Card className="anim-rise p-4"><PaneHeading className="mb-3 p-0">Findings by group</PaneHeading><div className="space-y-4">{facets.map((facet) => { const top = [...(facet.groups ?? [])].sort((a, b) => b.size - a.size).slice(0, 8); const maximum = top[0]?.size ?? 1; return <div key={facet.facet}><p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-grey">{scrub(facet.facet)}</p>{top.map((group) => <div key={group.label} className="mb-1 flex items-center gap-2"><Tooltip content={<p className="text-[12px] text-navy">{scrub(group.description)}</p>}><span className="w-32 shrink-0 truncate text-right text-[11.5px] font-medium text-navy">{scrub(group.label)}</span></Tooltip><span className="h-2 flex-1 bg-ground"><span className="anim-bar block h-full bg-blue" style={{ width: `${funnelBarWidth(group.size, maximum)}%` }} /></span><span className="w-5 text-[11px] font-bold text-navy">{group.size}</span></div>)}</div>; })}</div></Card></section>;
}

function LandscapeEmbed({ landscape }: { landscape: Landscape }) {
  const evidenceTypes = landscape.evidence_types ?? {};
  const years = landscape.years ?? {};
  const geographies = landscape.geographies === null || landscape.geographies === undefined ? {} : normaliseGeographies(landscape.geographies);
  const themes = orderThemes(landscape.themes ?? []);
  const hasDistributions = Object.keys(evidenceTypes).length > 0 || Object.keys(years).length > 0 || Object.keys(geographies).length > 0;
  return <>{hasDistributions && <section id="journey-landscape" className="scroll-mt-14"><Card className="anim-rise min-w-0 p-4"><PaneHeading className="mb-3 p-0">Evidence landscape</PaneHeading><div className="grid min-w-0 gap-4 lg:grid-cols-2">{Object.keys(evidenceTypes).length > 0 && <div className="min-w-0"><p className="mb-2 text-[12px] font-bold text-navy">Evidence types</p><EvidenceDistributionChart data={evidenceTypes} size="compact" /></div>}{Object.keys(years).length > 0 && <div className="min-w-0"><p className="mb-2 text-[12px] font-bold text-navy">Publication years</p><PublicationYearsChart data={years} size="compact" /></div>}{Object.keys(geographies).length > 0 && <div className="min-w-0 lg:col-span-2"><p className="mb-2 text-[12px] font-bold text-navy">Where sources were published</p><EvidenceDistributionChart data={geographies} size="compact" /><p className="mt-2 text-[11px] text-grey">Where sources were published, not where the studies were conducted.</p></div>}</div></Card></section>}{themes.length > 0 && <section id="journey-themes" className="scroll-mt-14"><Card className="anim-rise min-w-0 p-4"><PaneHeading className="mb-3 p-0">Themes in the evidence</PaneHeading><ul role="list" className="space-y-2.5">{themes.map((theme) => <li key={theme.name} className="flex min-w-0 items-baseline gap-2.5"><Chip tone="blue">{theme.size}</Chip><div className="min-w-0"><p className="break-words text-[13px] font-semibold text-navy">{scrub(theme.name)}</p><p className="break-words text-[12px] text-grey">{scrub(theme.description)}</p></div></li>)}</ul></Card></section>}</>;
}
