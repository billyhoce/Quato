import { useState } from "react"
import { Play, Loader2 } from "lucide-react"

interface BacktestConfigFormProps {
  hasStrategy: boolean
  onRun: (config: { start_date: string; end_date: string; capital_base: number }) => void
  isRunning: boolean
}

export function BacktestConfigForm({ hasStrategy, onRun, isRunning }: BacktestConfigFormProps) {
  const [startDate, setStartDate] = useState("2008-01-01")
  const [endDate, setEndDate] = useState("2011-12-31")
  const [capitalBase, setCapitalBase] = useState("100000")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onRun({
      start_date: startDate,
      end_date: endDate,
      capital_base: parseFloat(capitalBase),
    })
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-border p-4 space-y-3">
      <h3 className="text-sm font-semibold">Backtest</h3>

      <div className="space-y-2">
        <label className="block">
          <span className="text-xs text-muted-foreground">Start Date</span>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="mt-0.5 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="block">
          <span className="text-xs text-muted-foreground">End Date</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="mt-0.5 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="block">
          <span className="text-xs text-muted-foreground">Capital ($)</span>
          <input
            type="number"
            value={capitalBase}
            onChange={(e) => setCapitalBase(e.target.value)}
            min="1"
            className="mt-0.5 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
      </div>

      <button
        type="submit"
        disabled={!hasStrategy || isRunning}
        className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-primary text-primary-foreground
                   px-3 py-2 text-xs font-medium hover:opacity-90
                   disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
      >
        {isRunning ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Running...
          </>
        ) : (
          <>
            <Play className="w-3.5 h-3.5" />
            Run Backtest
          </>
        )}
      </button>
    </form>
  )
}
