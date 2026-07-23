// The workspace: an IDE-style chat column on the left (collapsible, resizable)
// and the artifact surface on the right — gallery, the new-job picker, or one
// artifact in detail.

import { useCallback, useEffect, useRef, useState } from 'react'
import { useWorkspace } from './workspace/context'
import ChatPanel from './workspace/ChatPanel'
import Gallery from './workspace/Gallery'
import ArtifactDetail from './workspace/ArtifactDetail'

const MIN_W = 300
const MAX_W = 640

export default function Workspace() {
  const ws = useWorkspace()
  const [width, setWidth] = useState(400)
  const [collapsed, setCollapsed] = useState(false)
  const dragging = useRef(false)

  // Reopening / starting a chat from elsewhere expands the rail
  useEffect(() => {
    if (ws.chatFocusToken > 0) setCollapsed(false)
  }, [ws.chatFocusToken])

  const onDown = useCallback(() => {
    dragging.current = true
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'
  }, [])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return
      setWidth(Math.min(MAX_W, Math.max(MIN_W, e.clientX)))
    }
    const onUp = () => {
      dragging.current = false
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [])

  const detailArtifact =
    ws.view.mode === 'detail' ? ws.getArtifact(ws.view.artifactId) : undefined

  return (
    <div className="flex h-[calc(100vh-58px)]">
      {collapsed ? (
        <button
          className="flex h-full w-10 shrink-0 flex-col items-center gap-2 border-r hairline bg-white pt-4 text-grey hover:text-navy"
          onClick={() => setCollapsed(false)}
          title="Open chat"
        >
          <span className="text-[16px]">»</span>
          <span className="[writing-mode:vertical-rl] text-[11px] font-bold uppercase tracking-wide">Chat</span>
        </button>
      ) : (
        <>
          <div className="h-full shrink-0" style={{ width }}>
            <ChatPanel onCollapse={() => setCollapsed(true)} />
          </div>
          <div
            className="group h-full w-1 shrink-0 cursor-col-resize bg-line transition-colors hover:bg-blue"
            onMouseDown={onDown}
            role="separator"
            aria-orientation="vertical"
          />
        </>
      )}

      <section className="min-w-0 flex-1 bg-ground">
        {detailArtifact ? <ArtifactDetail artifact={detailArtifact} /> : <Gallery />}
      </section>
    </div>
  )
}
