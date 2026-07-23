// The artifact detail: Output (the produced artifact) and Activity log (how it
// was made). Same tab grammar the journey used, now scoped to one artifact.

import { useEffect, useState } from 'react'
import { PaneH } from '../../ui'
import EvidenceBase from '../EvidenceBase'
import { capabilityById, type ArtifactRef } from './data'
import { useWorkspace } from './context'
import EvidenceActivity from './EvidenceActivity'

type Tab = 'output' | 'activity'

export default function ArtifactDetail({ artifact }: { artifact: ArtifactRef }) {
  const ws = useWorkspace()
  const cap = capabilityById(artifact.capability)

  // Planning evidence base opens on the Activity log (the plan + start button);
  // everything else opens on the Output.
  const defaultTab: Tab =
    artifact.kind === 'evidence' && artifact.status !== 'complete' ? 'activity' : 'output'
  const [tab, setTab] = useState<Tab>(defaultTab)
  useEffect(() => setTab(defaultTab), [artifact.id, defaultTab])

  return (
    <div className="flex h-full flex-col">
      <div className="border-b hairline bg-white px-5 pb-3 pt-4">
        <div className="flex items-start gap-2">
          <button
            className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center text-[22px] leading-none text-navy transition-colors hover:bg-ground focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue"
            onClick={ws.openGallery}
            title="Back"
            aria-label="Back to artifacts"
          >
            ‹
          </button>
          <div className="min-w-0 flex-1 pt-1">
            <div className="text-[10.5px] font-extrabold uppercase tracking-[.06em] text-blue">{cap.title}</div>
            <h2 className="mt-0.5 truncate font-display text-[19px] font-semibold text-navy">{artifact.title}</h2>
          </div>
        </div>
        <div className="mt-3 flex gap-5 pl-11">
          {(
            [
              ['output', 'Output'],
              ['activity', 'Activity log'],
            ] as [Tab, string][]
          ).map(([key, lab]) => (
            <button
              key={key}
              className={`border-b-2 pb-1 text-[12px] font-bold uppercase tracking-wide transition-colors ${
                tab === key ? 'border-blue text-navy' : 'border-transparent text-navy-40 hover:text-navy'
              }`}
              onClick={() => setTab(key)}
            >
              {lab}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 bg-ground">
        {artifact.kind === 'evidence' ? (
          tab === 'output' ? (
            <div className="thin-scroll h-full overflow-y-auto">
              <EvidenceBase embedded />
            </div>
          ) : (
            <EvidenceActivity />
          )
        ) : tab === 'output' ? (
          <MockOutput artifact={artifact} />
        ) : (
          <MockActivity artifact={artifact} />
        )}
      </div>
    </div>
  )
}

function MockOutput({ artifact }: { artifact: ArtifactRef }) {
  const m = artifact.mock!
  if (m.status === 'draft' || m.output.length === 0) {
    return (
      <div className="mx-auto max-w-[760px] px-8 py-16 text-center text-[13px] text-grey">
        Being drafted — brief the orchestrator in the chat, and the {capabilityById(m.capability).noun} appears here.
      </div>
    )
  }
  return (
    <div className="thin-scroll h-full overflow-y-auto">
      <main className="anim-rise mx-auto max-w-[780px] bg-white px-10 py-9 shadow-card ring-1 ring-line md:my-8">
        <div className="text-[11px] font-extrabold uppercase tracking-[.06em] text-navy-40">
          {capabilityById(m.capability).title} · version 1
        </div>
        <h1 className="mt-1 font-display text-[26px] font-extrabold leading-tight text-navy">{m.title}</h1>
        <p className="mt-1 text-[14px] text-grey">{m.subtitle}</p>
        <p className="mt-3 border-l-[3px] border-yellow-edge bg-yellow-tint px-3 py-2 text-[12px] text-navy">
          Illustrative mock content for the demo — not a real analysis.
        </p>
        {m.output.map((s) => (
          <section key={s.heading} className="mt-8">
            <h2 className="font-display text-[18px] font-bold text-navy">{s.heading}</h2>
            {s.body.map((p, i) => (
              <p key={i} className="mt-2 text-[14.5px] leading-[1.7] text-ink">{p}</p>
            ))}
          </section>
        ))}
      </main>
    </div>
  )
}

function MockActivity({ artifact }: { artifact: ArtifactRef }) {
  const m = artifact.mock!
  return (
    <div className="thin-scroll h-full overflow-y-auto px-7 py-6">
      <div className="card">
        <PaneH className="mb-3">How it was made</PaneH>
        <ol className="space-y-2.5">
          {m.activity.map((a, i) => (
            <li key={i} className="flex items-baseline gap-3 text-[13px] text-navy">
              <span className="w-14 shrink-0 text-[11px] tabular-nums text-grey">{a.at}</span>
              <span>{a.text}</span>
            </li>
          ))}
        </ol>
        <p className="mt-4 border-t hairline pt-3 text-[12px] text-grey">
          Illustrative mock activity for the demo.
        </p>
      </div>
    </div>
  )
}
