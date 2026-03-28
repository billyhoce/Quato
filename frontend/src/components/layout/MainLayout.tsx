import { useState, useCallback, useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Header } from "./Header"
import { Sidebar } from "./Sidebar"
import { ChatSidebar } from "./ChatSidebar"
import { ChatPanel } from "../chat/ChatPanel"
import { CodeViewerModal } from "../strategy/CodeViewerModal"
import { useStrategy, useStartBacktest, useBacktestStatus } from "../../api/hooks"
import { useSession } from "../../context/SessionContext"
import { apiFetch } from "../../api/client"
import type { StrategyResponse } from "../../api/types"
import { useQuery } from "@tanstack/react-query"

export function MainLayout() {
  const queryClient = useQueryClient()
  const { sessions, activeSessionId, createSession, switchSession, renameSession } = useSession()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [chatSidebarOpen, setChatSidebarOpen] = useState(false)
  const [codeModalOpen, setCodeModalOpen] = useState(false)
  const [hasStrategy, setHasStrategy] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)

  const strategyQuery = useStrategy(hasStrategy)
  const startBacktest = useStartBacktest()
  const backtestStatus = useBacktestStatus(activeTaskId)

  // Detect if switching to a session that already has a strategy
  const strategyProbe = useQuery({
    queryKey: ["strategyProbe", activeSessionId],
    queryFn: () => apiFetch<StrategyResponse>("/strategy/current"),
    staleTime: 0,
  })

  useEffect(() => {
    if (strategyProbe.data?.has_strategy) setHasStrategy(true)
  }, [strategyProbe.data])

  const isRunning =
    backtestStatus.data?.status === "running" || backtestStatus.data?.status === "queued"

  const handleStrategyUpdate = useCallback(() => {
    setHasStrategy(true)
  }, [])

  const handleRunBacktest = useCallback(
    (config: { start_date: string; end_date: string; capital_base: number }) => {
      startBacktest.mutate(config, {
        onSuccess: (data) => {
          setActiveTaskId(data.task_id)
        },
      })
    },
    [startBacktest]
  )

  const handleSwitchSession = useCallback(
    (id: string) => {
      switchSession(id)
      queryClient.invalidateQueries({ queryKey: ["strategy"] })
      queryClient.invalidateQueries({ queryKey: ["strategySummary"] })
      setHasStrategy(false)
      setActiveTaskId(null)
      setChatSidebarOpen(false)
    },
    [switchSession, queryClient]
  )

  const handleNewChat = useCallback(() => {
    createSession()
    queryClient.invalidateQueries({ queryKey: ["strategy"] })
    queryClient.invalidateQueries({ queryKey: ["strategySummary"] })
    setHasStrategy(false)
    setActiveTaskId(null)
    setChatSidebarOpen(false)
  }, [createSession, queryClient])

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <Header
        onToggleChatSidebar={() => setChatSidebarOpen((v) => !v)}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
      />
      <div className="flex flex-1 overflow-hidden">
        <ChatSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          open={chatSidebarOpen}
          onClose={() => setChatSidebarOpen(false)}
          onNewChat={handleNewChat}
          onSwitch={handleSwitchSession}
          onRename={renameSession}
        />
        <ChatPanel
          key={activeSessionId}
          sessionId={activeSessionId}
          onStrategyUpdate={handleStrategyUpdate}
        />
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          hasStrategy={hasStrategy}
          onViewCode={() => setCodeModalOpen(true)}
          onRunBacktest={handleRunBacktest}
          isRunning={isRunning || startBacktest.isPending}
        />
      </div>

      <CodeViewerModal
        open={codeModalOpen}
        onClose={() => setCodeModalOpen(false)}
        code={strategyQuery.data?.code ?? null}
      />
    </div>
  )
}
