import { useState } from "react"
import { History } from "lucide-react"
import { useBacktestHistory } from "../../api/hooks"
import { BacktestStatusBadge } from "./BacktestStatusBadge"
import { BacktestDetailModal } from "./BacktestDetailModal"
import { formatPercent } from "../../lib/utils"
import type { BacktestHistoryItem } from "../../api/types"

export function BacktestHistory() {
  const { data } = useBacktestHistory()
  const [selected, setSelected] = useState<BacktestHistoryItem | null>(null)

  const backtests = data?.backtests ?? []

  return (
    <>
      <div className="rounded-lg border border-border p-4 space-y-3">
        <div className="flex items-center gap-1.5">
          <History className="w-3.5 h-3.5 text-muted-foreground" />
          <h3 className="text-sm font-semibold">History</h3>
        </div>

        {backtests.length === 0 ? (
          <p className="text-xs text-muted-foreground">No backtests yet.</p>
        ) : (
          <div className="space-y-1.5 max-h-[240px] overflow-y-auto">
            {backtests.map((bt) => (
              <button
                key={bt.task_id}
                onClick={() => setSelected(bt)}
                className="w-full text-left rounded-md border border-border p-2 hover:bg-secondary/50
                           transition-colors text-xs"
              >
                <div className="flex items-center justify-between mb-1">
                  <BacktestStatusBadge status={bt.status} />
                  <span className="text-[10px] text-muted-foreground">
                    {new Date(bt.created_at).toLocaleDateString()}
                  </span>
                </div>
                {bt.status === "complete" && bt.success && bt.total_return != null && (
                  <span className={bt.total_return >= 0 ? "text-green-600" : "text-red-600"}>
                    {formatPercent(bt.total_return)}
                  </span>
                )}
                {bt.status === "failed" && (
                  <span className="text-red-600 truncate block">
                    {bt.error_message?.slice(0, 50) || "Failed"}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <BacktestDetailModal
        open={!!selected}
        onClose={() => setSelected(null)}
        backtest={selected}
      />
    </>
  )
}
