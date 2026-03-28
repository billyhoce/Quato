import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react"
import { setSessionIdGetter } from "../api/client"
import type { SessionMeta } from "../api/types"

const SESSIONS_KEY = "quato_sessions"
const ACTIVE_SESSION_KEY = "quato_active_session"
const LEGACY_SESSION_KEY = "quato_session_id"

// Module-level ref so setSessionIdGetter is called once but always reads current session
const activeSessionIdRef = { current: "" }
setSessionIdGetter(() => activeSessionIdRef.current)

function loadSessions(): SessionMeta[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    if (raw) return JSON.parse(raw) as SessionMeta[]
  } catch {
    // ignore
  }

  // Migration: carry over legacy single-session ID
  const legacyId = localStorage.getItem(LEGACY_SESSION_KEY)
  if (legacyId) {
    const session: SessionMeta = {
      id: legacyId,
      name: "New Chat",
      createdAt: new Date().toISOString(),
    }
    saveSessions([session])
    return [session]
  }

  return []
}

function saveSessions(sessions: SessionMeta[]) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions))
}

function createNewSession(): SessionMeta {
  return {
    id: crypto.randomUUID(),
    name: "New Chat",
    createdAt: new Date().toISOString(),
  }
}

interface SessionContextValue {
  sessions: SessionMeta[]
  activeSessionId: string
  createSession: () => string
  switchSession: (id: string) => void
  renameSession: (id: string, name: string) => void
  autoRenameSession: (id: string, name: string) => void
}

const SessionContext = createContext<SessionContextValue>({
  sessions: [],
  activeSessionId: "",
  createSession: () => "",
  switchSession: () => {},
  renameSession: () => {},
  autoRenameSession: () => {},
})

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<SessionMeta[]>(() => {
    const loaded = loadSessions()
    if (loaded.length === 0) {
      const initial = createNewSession()
      saveSessions([initial])
      return [initial]
    }
    return loaded
  })

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const stored = localStorage.getItem(ACTIVE_SESSION_KEY)
    const loaded = loadSessions()
    if (stored && loaded.some((s) => s.id === stored)) return stored
    return loaded[0]?.id ?? ""
  })

  // Keep module-level ref in sync
  activeSessionIdRef.current = activeSessionId

  useEffect(() => {
    localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId)
  }, [activeSessionId])

  const createSession = useCallback(() => {
    const session = createNewSession()
    setSessions((prev) => {
      const next = [session, ...prev]
      saveSessions(next)
      return next
    })
    setActiveSessionId(session.id)
    return session.id
  }, [])

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id)
  }, [])

  const renameSession = useCallback((id: string, name: string) => {
    setSessions((prev) => {
      const next = prev.map((s) => (s.id === id ? { ...s, name, userNamed: true } : s))
      saveSessions(next)
      return next
    })
  }, [])

  const autoRenameSession = useCallback((id: string, name: string) => {
    setSessions((prev) => {
      const session = prev.find((s) => s.id === id)
      if (session?.userNamed) return prev
      const next = prev.map((s) => (s.id === id ? { ...s, name } : s))
      saveSessions(next)
      return next
    })
  }, [])

  return (
    <SessionContext.Provider
      value={{ sessions, activeSessionId, createSession, switchSession, renameSession, autoRenameSession }}
    >
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  return useContext(SessionContext)
}

export function useSessionId() {
  return useContext(SessionContext).activeSessionId
}
