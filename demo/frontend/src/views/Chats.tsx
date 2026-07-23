// Chats library — past conversations for this project. Clicking one reopens it
// in the Workspace rail; closing a rail tab archives here, it doesn't delete.

import { useNavigate, useParams } from 'react-router-dom'
import { useWorkspace } from './workspace/context'

export default function Chats() {
  const { id } = useParams<{ id: string }>()
  const ws = useWorkspace()
  const navigate = useNavigate()

  const open = (chatId: string) => {
    ws.reopenChat(chatId)
    navigate(`/project/${id}`)
  }

  return (
    <main className="mx-auto max-w-[860px] px-8 py-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[24px] font-extrabold text-navy">Chats</h1>
          <p className="mt-1 text-[13px] text-grey">
            Past conversations for this project. Open one to continue in the Workspace.
          </p>
        </div>
        <button
          className="btn"
          onClick={() => {
            ws.newChat()
            navigate(`/project/${id}`)
          }}
        >
          + New chat
        </button>
      </div>

      <div className="bg-white shadow-card ring-1 ring-line">
        {ws.chatHistory.map((c) => {
          const contextTitles = c.contextIds
            .map((aid) => ws.getArtifact(aid)?.title)
            .filter(Boolean) as string[]
          return (
            <div
              key={c.id}
              role="button"
              tabIndex={0}
              className="group flex cursor-pointer items-start gap-4 border-b hairline px-5 py-4 text-left last:border-b-0 hover:bg-blue-tint2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue"
              onClick={() => open(c.id)}
              onKeyDown={(e) => e.key === 'Enter' && open(c.id)}
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-bold text-navy">{c.title}</span>
                  {c.open && <span className="chip chip--blue !py-0.5">Open</span>}
                </div>
                <p className="mt-1 line-clamp-2 text-[12.5px] leading-snug text-grey">{c.preview}</p>
                {contextTitles.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {contextTitles.map((t) => (
                      <span key={t} className="chip chip--soft !py-0.5">{t}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex shrink-0 flex-col items-end gap-2">
                <span className="text-[11.5px] text-grey">{c.updatedAt}</span>
                {c.kind !== 'primary' && (
                  <button
                    className="btn btn--ghost !px-2 !py-0.5 !text-[11.5px] opacity-0 group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation()
                      ws.deleteChat(c.id)
                    }}
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>
          )
        })}
        {ws.chatHistory.length === 0 && (
          <p className="px-5 py-10 text-center text-[13px] text-grey">
            No chats yet — start one from the Workspace.
          </p>
        )}
      </div>
    </main>
  )
}
