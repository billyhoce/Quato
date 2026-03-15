import { createContext, useContext, useMemo, type ReactNode } from "react"
import { setSessionIdGetter } from "../api/client"

const SESSION_KEY = "quato_session_id"

function getOrCreateSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(SESSION_KEY, id)
  }
  return id
}

const SessionContext = createContext<string>("")

export function SessionProvider({ children }: { children: ReactNode }) {
  const sessionId = useMemo(() => {
    const id = getOrCreateSessionId()
    setSessionIdGetter(() => id)
    return id
  }, [])

  return (
    <SessionContext.Provider value={sessionId}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSessionId() {
  return useContext(SessionContext)
}
