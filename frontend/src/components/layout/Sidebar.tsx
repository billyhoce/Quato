import { X } from "lucide-react"
import { StrategySummary } from "../strategy/StrategySummary"
import { BacktestConfigForm } from "../backtest/BacktestConfigForm"
import { BacktestHistory } from "../backtest/BacktestHistory"
import { UniverseList } from "../universes/UniverseList"

interface SidebarProps {
  open: boolean
  onClose: () => void
  hasStrategy: boolean
  onViewCode: () => void
  onRunBacktest: (config: { bundle: string; start_date: string; end_date: string; capital_base: number }) => void
  isRunning: boolean
}

export function Sidebar({ open, onClose, hasStrategy, onViewCode, onRunBacktest, isRunning }: SidebarProps) {
  return (
    <>
      {/* Overlay for mobile */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-30 md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`
          fixed md:relative z-40 md:z-auto
          top-0 right-0 h-full w-[460px] bg-card border-l border-border
          flex flex-col overflow-y-auto
          transition-transform duration-200
          ${open ? "translate-x-0" : "translate-x-full md:translate-x-0"}
        `}
      >
        <div className="flex items-center justify-between p-4 md:hidden">
          <span className="font-semibold">Menu</span>
          <button onClick={onClose} className="p-1 rounded hover:bg-secondary">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex flex-col gap-4 p-4 overflow-y-auto flex-1">
          <StrategySummary hasStrategy={hasStrategy} onViewCode={onViewCode} />
          <BacktestConfigForm
            hasStrategy={hasStrategy}
            onRun={onRunBacktest}
            isRunning={isRunning}
          />
          <BacktestHistory />
          <UniverseList />
        </div>
      </aside>
    </>
  )
}
