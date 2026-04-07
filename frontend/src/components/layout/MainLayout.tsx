import { useState, useCallback, useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Header } from "./Header"
import { Sidebar } from "./Sidebar"
import { ChatSidebar } from "./ChatSidebar"
import { ChatPanel } from "../chat/ChatPanel"
import { CodeViewerModal } from "../strategy/CodeViewerModal"
import { useStrategy, useBacktestHistory } from "../../api/hooks"
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
  const [pendingChatMessage, setPendingChatMessage] = useState<
    { content: string; isSystem: boolean } | null
  >(null)
  const [isChatPending, setIsChatPending] = useState(false)

  // Backtest watcher — tracks which task completions have already triggered a notification
  const [watcherInitialized, setWatcherInitialized] = useState(false)
  const seenTaskIdsRef = useRef<Set<string>>(new Set())

  // Poll history every 5s so the watcher can detect new completions/failures
  const { data: backtestHistory } = useBacktestHistory({ refetchInterval: 5000 })

  // Effect 1: On first successful history fetch, mark all existing completed/failed tasks as
  // already seen so we don't fire stale notifications on page load or session switch.
  useEffect(() => {
    if (!watcherInitialized && backtestHistory) {
      backtestHistory.backtests
        .filter((t) => t.status === "complete" || t.status === "failed")
        .forEach((t) => seenTaskIdsRef.current.add(t.task_id))
      setWatcherInitialized(true)
    }
  }, [backtestHistory, watcherInitialized])

  // Effect 2: Watch for new completions/failures belonging to the active session.
  useEffect(() => {
    if (!watcherInitialized || !backtestHistory) return

    for (const task of backtestHistory.backtests) {
      if (task.session_id !== activeSessionId) continue
      if (task.status !== "complete" && task.status !== "failed") continue
      if (seenTaskIdsRef.current.has(task.task_id)) continue

      // Mark seen before setting state to prevent duplicate fires on re-render
      seenTaskIdsRef.current.add(task.task_id)

      const content =
        task.status === "complete"
          ? `Backtest completed — task ${task.task_id}. Please review the results and summarise performance for the user.`
          : `Backtest failed — task ${task.task_id}. Please check the error and fix the strategy for a retry, or explain the issue if it cannot be fixed.`

      setPendingChatMessage({ content, isSystem: true })
      break // One notification per effect pass; the next poll cycle handles the rest
    }
  }, [backtestHistory, watcherInitialized, activeSessionId])

  const strategyQuery = useStrategy(hasStrategy)

  // Detect if switching to a session that already has a strategy
  const strategyProbe = useQuery({
    queryKey: ["strategyProbe", activeSessionId],
    queryFn: () => apiFetch<StrategyResponse>("/strategy/current"),
    staleTime: 0,
  })

  useEffect(() => {
    if (strategyProbe.data?.has_strategy) setHasStrategy(true)
  }, [strategyProbe.data])

  const handleStrategyUpdate = useCallback(() => {
    setHasStrategy(true)
  }, [])

  const handleRunBacktest = useCallback(
    (config: { bundle: string; start_date: string; end_date: string; capital_base: number }) => {
      const msg = [
        "Please run a backtest with the following parameters:",
        `- Bundle: ${config.bundle}`,
        `- Start date: ${config.start_date}`,
        `- End date: ${config.end_date}`,
        `- Capital base: $${config.capital_base.toLocaleString()}`,
        `- Session ID: ${activeSessionId}`,
      ].join("\n")
      setPendingChatMessage({ content: msg, isSystem: false })
    },
    [activeSessionId]
  )

  const handleSwitchSession = useCallback(
    (id: string) => {
      switchSession(id)
      queryClient.invalidateQueries({ queryKey: ["strategy"] })
      queryClient.invalidateQueries({ queryKey: ["strategySummary"] })
      setHasStrategy(false)
      setPendingChatMessage(null)
      setChatSidebarOpen(false)
      // Reset watcher so Effect 1 re-runs for the new session's history snapshot
      seenTaskIdsRef.current = new Set()
      setWatcherInitialized(false)
    },
    [switchSession, queryClient]
  )

  const handleNewChat = useCallback(() => {
    createSession()
    queryClient.invalidateQueries({ queryKey: ["strategy"] })
    queryClient.invalidateQueries({ queryKey: ["strategySummary"] })
    setHasStrategy(false)
    setPendingChatMessage(null)
    setChatSidebarOpen(false)
    seenTaskIdsRef.current = new Set()
    setWatcherInitialized(false)
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
          pendingMessage={pendingChatMessage}
          onPendingMessageHandled={() => setPendingChatMessage(null)}
          onPendingChange={setIsChatPending}
        />
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          hasStrategy={hasStrategy}
          onViewCode={() => setCodeModalOpen(true)}
          onRunBacktest={handleRunBacktest}
          isRunning={isChatPending}
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
