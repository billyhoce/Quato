import { useState, useCallback } from "react"
import { Header } from "./Header"
import { Sidebar } from "./Sidebar"
import { ChatPanel } from "../chat/ChatPanel"
import { CodeViewerModal } from "../strategy/CodeViewerModal"
import { useStrategy, useStartBacktest, useBacktestStatus } from "../../api/hooks"

export function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [codeModalOpen, setCodeModalOpen] = useState(false)
  const [hasStrategy, setHasStrategy] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)

  const strategyQuery = useStrategy(hasStrategy)
  const startBacktest = useStartBacktest()
  const backtestStatus = useBacktestStatus(activeTaskId)

  const isRunning = backtestStatus.data?.status === "running" || backtestStatus.data?.status === "queued"

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

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <Header onToggleSidebar={() => setSidebarOpen((v) => !v)} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          hasStrategy={hasStrategy}
          onViewCode={() => setCodeModalOpen(true)}
          onRunBacktest={handleRunBacktest}
          isRunning={isRunning || startBacktest.isPending}
        />
        <ChatPanel onStrategyUpdate={handleStrategyUpdate} />
      </div>

      <CodeViewerModal
        open={codeModalOpen}
        onClose={() => setCodeModalOpen(false)}
        code={strategyQuery.data?.code ?? null}
      />
    </div>
  )
}
