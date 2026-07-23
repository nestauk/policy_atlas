// The evidence base — the demo's closing shot. Claims are typed spans of the
// running prose; hover shows provenance, click opens the exact source passage
// highlighted in context. The annotation layer lives IN the text.

import { Fragment, useEffect, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  api,
  type Artefact,
  type ArtefactSection,
  type Block,
  type ChunkContext,
  type Citation,
  type Claim,
  type LiveSection,
} from '../api'
import { SourceLink } from '../sourcePanel'
import { useProject } from '../store'
import { Dot, PaneH, SlideOver, Tip, TIER_LABEL, TIER_TEXT } from '../ui'

export default function EvidenceBase({ embedded = false }: { embedded?: boolean } = {}) {
  const { id } = useParams<{ id: string }>()
  const { state } = useProject()
  const [artefact, setArtefact] = useState<Artefact | null>(null)
  const [detail, setDetail] = useState<Claim | null>(null)

  useEffect(() => {
    api.getArtefact(id!).then(setArtefact).catch(() => {})
  }, [id, state.phase])

  const outerClass = embedded ? '' : 'min-h-[calc(100vh-58px)]'

  if (!artefact) {
    if (state.liveSections.length > 0) return <LiveArtefact sections={state.liveSections} embedded={embedded} />
    return (
      <div className="mx-auto max-w-[760px] px-8 py-16 text-center text-[13px] text-grey">
        The evidence base appears here once the analysis has written it.
      </div>
    )
  }

  const cs = artefact.coverage_snapshot
  const topTypes = Object.entries(cs.study_types).sort(([, a], [, b]) => b - a)
  const shownTypes = topTypes.slice(0, 3)
  const checkinResolved = state.thread.some((m) => m.checkin?.resolved)

  return (
    <div className={outerClass}>
      <main className="anim-rise mx-auto max-w-[780px] bg-white px-10 py-9 shadow-card ring-1 ring-line md:my-8">
        <div className="flex items-center gap-2 text-[12.5px] text-grey">
          <Dot tone="done" /> Ready — produced by Policy Atlas
          {checkinResolved && <span>· check-in resolved</span>}
        </div>
        <div className="mt-3 text-[11px] font-extrabold uppercase tracking-[.06em] text-navy-40">
          Evidence base · version 1
        </div>
        <h1 className="mt-1 font-display text-[26px] font-extrabold leading-tight text-navy">{artefact.title}</h1>
        <p className="mt-1 text-[14px] text-grey">{artefact.question}</p>

        <div className="mt-5 grid grid-cols-2 border hairline sm:grid-cols-4">
          {[
            ['Sources', `${cs.source_count} found · ${cs.included} included`],
            ['Study types', shownTypes.map(([k, v]) => `${v} ${k.toLowerCase()}`).join(' · ') + (topTypes.length > 3 ? ` · +${topTypes.length - 3} more` : '')],
            ['Years', cs.year_range ? `${cs.year_range.min}–${cs.year_range.max}` : '—'],
            ['Screened out', `${cs.screened_out} — all listed with reasons`],
          ].map(([label, value]) => (
            <div key={label} className="border-r hairline p-3 last:border-r-0">
              <PaneH>{label}</PaneH>
              <div className="mt-1 text-[12.5px] font-medium leading-snug text-navy">{value}</div>
            </div>
          ))}
        </div>

        {artefact.key_findings && (
          <SectionBlocks section={artefact.key_findings} onOpen={setDetail} className="mt-7" />
        )}

        {artefact.sections.map((section) => (
          <SectionBlocks key={section.title} section={section} onOpen={setDetail} className="mt-9" />
        ))}

        {artefact.conclusion && (
          <SectionBlocks
            section={artefact.conclusion}
            onOpen={setDetail}
            className="mt-10 border-t hairline pt-6"
          />
        )}

        <section className="mt-10 border-t hairline pt-6">
          <h2 className="font-display text-[18px] font-bold text-navy">References</h2>
          <ol className="mt-3 space-y-2">
            {artefact.references.map((r) => (
              <li key={r.n} className="flex gap-3 text-[13px] leading-snug">
                <span className="shrink-0 font-bold text-navy">[{r.n}]</span>
                <span>
                  <SourceLink title={r.title}>{r.title}</SourceLink>
                  <span className="italic text-grey">
                    {r.venue ? ` — ${r.venue}` : ''}{r.year ? `, ${r.year}` : ''}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </section>
      </main>

      {!embedded && (
        <Link to={`/project/${id}`} className="btn fixed bottom-6 left-6 z-30">Ask Policy Atlas</Link>
      )}

      <ClaimPanel claim={detail} onClose={() => setDetail(null)} projectId={id!} />
    </div>
  )
}

/* --- typed annotation rendering: the prose IS the claims --- */

const SPAN_STYLE: Record<Claim['claim_type'], string> = {
  citation: 'border-b border-dotted border-blue-edge hover:bg-blue-tint2',
  gap: 'border-b border-dotted border-yellow-edge hover:bg-yellow-tint',
  reasoning: 'border-b border-dashed border-line-2 hover:bg-ground',
  pattern: 'border-b border-dotted border-violet hover:bg-blue-tint2',
  theme: 'border-b border-dotted border-violet hover:bg-blue-tint2',
  unspanned_assertion: 'border-b border-dotted border-orange-edge hover:bg-orange-tint',
}

const TYPE_HINT: Record<Claim['claim_type'], string> = {
  citation: '',
  gap: 'Evidence gap — recorded, never glossed over.',
  reasoning: 'Reasoning from the evidence — not a quoted source.',
  pattern: 'A computed pattern across the evidence.',
  theme: "The clustering's reading of the corpus.",
  unspanned_assertion: 'A source-check flag from the grounding review.',
}

const TYPE_LABEL: Record<Claim['claim_type'], string> = {
  citation: '',
  gap: 'gap',
  reasoning: 'reasoning',
  pattern: 'pattern',
  theme: 'theme',
  unspanned_assertion: 'source check',
}

function SectionBlocks({
  section,
  onOpen,
  className = '',
}: {
  section: ArtefactSection
  onOpen: (c: Claim) => void
  className?: string
}) {
  const blocks = section.blocks.filter((b) => b.prose.trim() || b.claims.length > 0)
  if (blocks.length === 0) return null
  return (
    <section className={className}>
      <h2 className="font-display text-[18px] font-bold text-navy">{section.title}</h2>
      {blocks.map((b) => (
        <BlockProse key={b.block_id} block={b} onOpen={onOpen} />
      ))}
    </section>
  )
}

function BlockProse({ block, onOpen }: { block: Block; onOpen: (c: Claim) => void }) {
  const prose = block.prose
  if (!prose.trim() && block.claims.length === 0) return null
  const claims = [...block.claims]
    .filter((c) => c.span && c.span.end != null && c.span.start >= 0)
    .sort((a, b) => a.span!.start - b.span!.start)

  const parts: ReactNode[] = []
  let cursor = 0
  for (const claim of claims) {
    const { start } = claim.span!
    const end = claim.span!.end!
    if (start < cursor || end > prose.length) continue // overlapping/oversize: skip honestly
    if (start > cursor) parts.push(<Fragment key={`t${cursor}`}>{prose.slice(cursor, start)}</Fragment>)
    parts.push(<ClaimSpan key={claim.claim_id} claim={claim} text={prose.slice(start, end)} onOpen={onOpen} />)
    cursor = end
  }
  if (cursor < prose.length) parts.push(<Fragment key="tail">{prose.slice(cursor)}</Fragment>)

  return (
    <p className="mt-3 whitespace-pre-line text-[14.5px] leading-[1.7] text-ink">
      {parts}
    </p>
  )
}

function ClaimSpan({ claim, text, onOpen }: { claim: Claim; text: string; onOpen: (c: Claim) => void }) {
  const first = claim.citations[0]
  const tip = (
    <div className="max-w-[260px] space-y-1.5 text-[12px] leading-snug">
      {first ? (
        <>
          <div className="font-semibold text-navy">{first.source_title}</div>
          {first.quote && <div className="italic text-grey">“{first.quote.slice(0, 180)}{first.quote.length > 180 ? '…' : ''}”</div>}
          {first.grounding_tier && <div className="text-grey">{TIER_LABEL[first.grounding_tier] ?? first.grounding_tier}</div>}
          <div className="text-[11px] text-navy-40">Click to view in context</div>
        </>
      ) : (
        <div className="text-navy">{TYPE_HINT[claim.claim_type] || 'Claim'}</div>
      )}
    </div>
  )
  return (
    <Tip content={tip}>
      <span
        role="button"
        tabIndex={0}
        className={`cursor-pointer transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue ${SPAN_STYLE[claim.claim_type]}`}
        onClick={() => onOpen(claim)}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onOpen(claim))}
      >
        {text}
        {claim.claim_type === 'citation' && claim.citations.length > 0 && (
          <span className="chip chip--blue mx-1 !px-1.5 !py-0 !text-[10.5px] align-[2px]">
            [{[...new Set(claim.citations.map((c) => c.n))].join(',')}]
          </span>
        )}
        {claim.claim_type !== 'citation' && (
          <span className={`chip mx-1 !px-1.5 !py-0 !text-[10px] align-[2px] ${claim.claim_type === 'gap' ? 'chip--yellow' : 'chip--soft'}`}>
            {TYPE_LABEL[claim.claim_type]}
          </span>
        )}
      </span>
    </Tip>
  )
}

/* --- provenance panel: quote highlighted in its source context --- */

function ClaimPanel({ claim, onClose, projectId }: { claim: Claim | null; onClose: () => void; projectId: string }) {
  return (
    <SlideOver open={!!claim} onClose={onClose} title="Where this comes from">
      {claim && (
        <div className="space-y-5">
          <p className="border-l-2 border-blue-edge pl-3 text-[13.5px] font-medium leading-snug text-navy">
            {claim.text}
          </p>
          {claim.claim_type === 'gap' && (
            <p className="border-l-[3px] border-yellow-edge bg-yellow-tint p-3 text-[13px] text-navy">
              This is a recorded evidence gap: the analysis looked and found the base thin here.
              Gaps are part of the answer, never glossed over.
            </p>
          )}
          {claim.claim_type === 'reasoning' && (
            <p className="text-[12.5px] text-grey">{TYPE_HINT.reasoning}</p>
          )}
          {claim.claim_type === 'unspanned_assertion' && (
            <p className="border-l-[3px] border-orange bg-orange-tint p-3 text-[13px] text-navy">
              {TYPE_HINT.unspanned_assertion}
            </p>
          )}
          {claim.citations.map((c, i) => (
            <CitationContext key={i} citation={c} projectId={projectId} />
          ))}
          <p className="border-t hairline pt-3 text-[11px] text-grey">
            Every claim links to the exact passage it came from.
          </p>
        </div>
      )}
    </SlideOver>
  )
}

function CitationContext({ citation, projectId }: { citation: Citation; projectId: string }) {
  const [ctx, setCtx] = useState<ChunkContext | null>(null)
  useEffect(() => {
    setCtx(null)
    api.getChunkContext(projectId, citation.chunk_id).then(setCtx).catch(() => {})
  }, [projectId, citation.chunk_id])

  return (
    <div className="border hairline p-4">
      <div className="text-[13px] font-bold leading-snug text-blue">
        [{citation.n}] <SourceLink title={citation.source_title}>{citation.source_title}</SourceLink>
      </div>
      {ctx && (
        <div className="mt-0.5 text-[11.5px] text-grey">
          {[ctx.year, ctx.venue].filter(Boolean).join(' · ')}
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {citation.verified && <span className="chip chip--green">Verified quote</span>}
        {citation.grounding_tier && (
          <Tip content={<div className="text-[12px] text-navy">{TIER_TEXT[citation.grounding_tier] ?? ''}</div>}>
            <span className="chip chip--soft cursor-default">{TIER_LABEL[citation.grounding_tier] ?? citation.grounding_tier}</span>
          </Tip>
        )}
        {citation.appraisal_label && <span className="chip chip--blue">{citation.appraisal_label}</span>}
      </div>
      <div className="mt-3 space-y-2 text-[12.5px] leading-relaxed">
        {ctx ? (
          <>
            {ctx.previous && <p className="text-grey">{ctx.previous}</p>}
            <p className="text-navy"><Highlighted text={ctx.content} quote={citation.quote} /></p>
            {ctx.next && <p className="text-grey">{ctx.next}</p>}
          </>
        ) : (
          <p className="italic text-grey">“{citation.quote}”</p>
        )}
      </div>
    </div>
  )
}

function Highlighted({ text, quote }: { text: string; quote: string }) {
  // exact match, then whitespace-normalised fallback; never fail the panel
  let start = text.indexOf(quote)
  let end = start + quote.length
  if (start < 0) {
    const squash = (s: string) => s.replace(/\s+/g, ' ')
    const idx = squash(text).indexOf(squash(quote))
    if (idx >= 0) {
      // map squashed index back approximately by scanning
      let raw = 0
      let sq = 0
      while (sq < idx && raw < text.length) {
        raw += 1
        sq = squash(text.slice(0, raw)).length
      }
      start = raw
      end = Math.min(start + quote.length + 20, text.length)
    }
  }
  if (start < 0) {
    return (
      <>
        <span className="mb-1 block italic text-grey">“{quote}”</span>
        {text}
      </>
    )
  }
  return (
    <>
      {text.slice(0, start)}
      <mark className="bg-yellow-tint font-medium text-navy">{text.slice(start, end)}</mark>
      {text.slice(end)}
    </>
  )
}

// The artefact-in-progress: the streamed section skeleton fills in as the
// synthesis writes each section. Citations/provenance arrive with the final
// read model once the run commits — the prose here is the persisted prose.
function LiveArtefact({ sections, embedded = false }: { sections: LiveSection[]; embedded?: boolean }) {
  return (
    <div className={embedded ? '' : 'min-h-[calc(100vh-58px)]'}>
      <main className="anim-rise mx-auto max-w-[780px] bg-white px-10 py-9 shadow-card ring-1 ring-line md:my-8">
        <div className="flex items-center gap-2 text-[12.5px] text-grey">
          <Dot tone="progress" /> Being written now — sections appear as they are drafted
        </div>
        {sections.map((s) => (
          <section key={s.title} className="mt-9">
            <h2 className="font-display text-[18px] font-bold text-navy">{s.title}</h2>
            {s.status === 'done' && s.content ? (
              <p className="anim-rise mt-2 whitespace-pre-line text-[14.5px] leading-relaxed text-navy">
                {s.content}
              </p>
            ) : s.status === 'writing' ? (
              <p className="mt-2 flex items-center gap-2 text-[13px] text-grey">
                <Dot tone="progress" /> Writing this section now…
              </p>
            ) : (
              <p className="mt-2 text-[13px] italic text-grey">{s.focus || 'Waiting to be written.'}</p>
            )}
          </section>
        ))}
        <p className="mt-10 border-t hairline pt-4 text-[12px] text-grey">
          Citations and source provenance are attached when the write-up completes and is checked.
        </p>
      </main>
    </div>
  )
}
