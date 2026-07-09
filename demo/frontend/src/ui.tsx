// Shared primitives: chips, tooltips, slide-over, animated numbers, bars.
// Everything sharp-cornered, hairline-bordered, board-room legible.

import {
  useEffect, useRef, useState, type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

export function PaneH({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`pane-h ${className}`}>{children}</div>
}

export function Dot({ tone }: { tone: 'progress' | 'done' | 'paused' | 'idle' }) {
  const bg = { progress: 'bg-yellow', done: 'bg-green', paused: 'bg-orange', idle: 'bg-line-2' }[tone]
  return <span className={`dot ${bg}`} />
}

// Animated count-up: numbers arriving is the product working.
export function CountUp({ value, className = '' }: { value: number; className?: string }) {
  const [shown, setShown] = useState(value)
  const fromRef = useRef(value)
  useEffect(() => {
    const from = fromRef.current
    if (from === value) return
    fromRef.current = value
    const t0 = performance.now()
    const dur = 600
    let raf = 0
    const tick = (t: number) => {
      const k = Math.min((t - t0) / dur, 1)
      setShown(Math.round(from + (value - from) * (1 - (1 - k) ** 3)))
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value])
  return <span className={className}>{shown}</span>
}

export function HBar({ value, max, tone = 'bg-blue' }: { value: number; max: number; tone?: string }) {
  return (
    <div className="relative h-2 flex-1 bg-blue-tint">
      <div className={`anim-bar h-2 ${tone}`} style={{ width: `${Math.min(Math.max((value / Math.max(max, 1)) * 100, value > 0 ? 3 : 0), 100)}%` }} />
    </div>
  )
}

export function formatElapsed(secs: number): string {
  if (secs < 60) return `${Math.round(secs)}s`
  const m = Math.floor(secs / 60)
  const s = Math.round(secs % 60)
  return s === 0 ? `${m}m` : `${m}m ${s}s`
}

// --- tooltip: body portal so tables/scroll clipping never hide it ---

export function Tip({ content, children, maxWidth = 280, className = '' }: {
  content: ReactNode
  children: ReactNode
  maxWidth?: number
  className?: string
}) {
  const anchor = useRef<HTMLSpanElement>(null)
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)

  const show = () => {
    const r = anchor.current?.getBoundingClientRect()
    if (r) setPos({ x: Math.min(r.left, window.innerWidth - maxWidth - 16), y: r.bottom + 6 })
  }
  const hide = () => setPos(null)

  return (
    <span
      ref={anchor}
      className={className}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {pos &&
        createPortal(
          <div
            className="pointer-events-none fixed z-[70] border border-line-2 bg-white p-2.5 shadow-panel"
            style={{ left: pos.x, top: pos.y, maxWidth }}
            role="tooltip"
          >
            {content}
          </div>,
          document.body,
        )}
    </span>
  )
}

// --- right slide-over ---

export function SlideOver({ open, onClose, title, children, z = 40 }: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  z?: number
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return createPortal(
    <>
      <div
        className="fixed inset-0 bg-navy/20"
        style={{ zIndex: z }}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="anim-slide-in thin-scroll fixed inset-y-0 right-0 w-full max-w-[460px] overflow-y-auto bg-white shadow-panel"
        style={{ zIndex: z + 1 }}
        role="dialog"
        aria-label={title}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b hairline bg-white px-5 py-3.5">
          <PaneH>{title}</PaneH>
          <button className="btn btn--ghost !p-1 text-[15px]" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="p-5">{children}</div>
      </aside>
    </>,
    document.body,
  )
}

// --- small helpers ---

export function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-1.5">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-[12px] text-grey">{k}</dt>
          <dd className="text-[13px] font-medium text-navy">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Spinner() {
  return <span className="anim-spin inline-block h-3 w-3 rounded-full border-2 border-blue border-t-transparent" aria-hidden />
}

export const TIER_TEXT: Record<string, string> = {
  tier_1: 'Direct quote, verified against the source',
  tier_2: 'Grounded in a specific passage',
  tier_3: 'Supported across passages',
  tier_4: 'Reasoning from the evidence, not a quote',
  unsupported_mis_cited: 'Failed verification — flagged, never hidden',
}

export const TIER_LABEL: Record<string, string> = {
  tier_1: 'Tier 1 · direct quote',
  tier_2: 'Tier 2 · grounded',
  tier_3: 'Tier 3 · supported',
  tier_4: 'Tier 4 · reasoning',
  unsupported_mis_cited: 'Unsupported — flagged',
}
