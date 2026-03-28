import { useState, useRef, useEffect } from "react"
import { X, Plus, Pencil } from "lucide-react"
import type { SessionMeta } from "../../api/types"

interface ChatSidebarProps {
  sessions: SessionMeta[]
  activeSessionId: string
  open: boolean
  onClose: () => void
  onNewChat: () => void
  onSwitch: (id: string) => void
  onRename: (id: string, name: string) => void
}

function SessionItem({
  session,
  isActive,
  onSwitch,
  onRename,
}: {
  session: SessionMeta
  isActive: boolean
  onSwitch: () => void
  onRename: (name: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(session.name)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) inputRef.current?.select()
  }, [editing])

  // Keep value in sync if name changes externally (e.g. auto-rename)
  useEffect(() => {
    if (!editing) setValue(session.name)
  }, [session.name, editing])

  function commit() {
    const trimmed = value.trim()
    if (trimmed && trimmed !== session.name) onRename(trimmed)
    setEditing(false)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") commit()
    if (e.key === "Escape") { setValue(session.name); setEditing(false) }
  }

  return (
    <div className={`
      group relative flex items-center rounded-md mb-1
      ${isActive ? "bg-secondary" : "hover:bg-secondary"}
      transition-colors
    `}>
      <button
        onClick={onSwitch}
        onDoubleClick={(e) => { e.preventDefault(); setEditing(true) }}
        className="flex-1 text-left px-3 py-2 text-sm min-w-0"
      >
        {editing ? (
          <input
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={commit}
            onKeyDown={handleKeyDown}
            onClick={(e) => e.stopPropagation()}
            className="w-full bg-transparent outline-none font-medium truncate"
          />
        ) : (
          <>
            <div className="truncate font-medium">{session.name}</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {new Date(session.createdAt).toLocaleDateString()}
            </div>
          </>
        )}
      </button>

      {!editing && (
        <button
          onClick={(e) => { e.stopPropagation(); setEditing(true) }}
          className="shrink-0 p-1.5 mr-1 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-secondary-foreground/10"
          title="Rename"
        >
          <Pencil className="w-3 h-3 text-muted-foreground" />
        </button>
      )}
    </div>
  )
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  open,
  onClose,
  onNewChat,
  onSwitch,
  onRename,
}: ChatSidebarProps) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-30 md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`
          fixed md:relative z-40 md:z-auto
          top-0 left-0 h-full w-[260px] bg-card border-r border-border
          flex flex-col overflow-hidden
          transition-transform duration-200
          ${open ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
      >
        <div className="flex items-center justify-between p-4 md:hidden">
          <span className="font-semibold">Chats</span>
          <button onClick={onClose} className="p-1 rounded hover:bg-secondary">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-3">
          <button
            onClick={onNewChat}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {sessions.map((session) => (
            <SessionItem
              key={session.id}
              session={session}
              isActive={session.id === activeSessionId}
              onSwitch={() => onSwitch(session.id)}
              onRename={(name) => onRename(session.id, name)}
            />
          ))}
        </div>
      </aside>
    </>
  )
}
