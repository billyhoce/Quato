import { X, Download, FileText } from "lucide-react"
import { BacktestResultCard } from "./BacktestResultCard"
import { BacktestStatusBadge } from "./BacktestStatusBadge"
import { apiFetch } from "../../api/client"
import type { BacktestDownloadResponse, BacktestHistoryItem } from "../../api/types"

interface BacktestDetailModalProps {
  open: boolean
  onClose: () => void
  backtest: BacktestHistoryItem | null
}

async function openDownload(taskId: string, type: "download" | "tearsheet") {
  try {
    const data = await apiFetch<BacktestDownloadResponse>(`/backtest/${taskId}/${type}`)
    window.open(data.download_url, "_blank")
  } catch {
    // silently fail if not available
  }
}

export function BacktestDetailModal({ open, onClose, backtest }: BacktestDetailModalProps) {
  if (!open || !backtest) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-card rounded-xl shadow-xl w-full max-w-sm mx-4">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-sm">Backtest Details</h2>
            <BacktestStatusBadge status={backtest.status} />
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-secondary text-muted-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="text-xs text-muted-foreground">
            <p>Created: {new Date(backtest.created_at).toLocaleString()}</p>
            {backtest.completed_at && (
              <p>Completed: {new Date(backtest.completed_at).toLocaleString()}</p>
            )}
          </div>

          {backtest.status === "complete" && backtest.success && (
            <>
              <BacktestResultCard
                totalReturn={backtest.total_return}
                sharpeRatio={backtest.sharpe_ratio}
                maxDrawdown={backtest.max_drawdown}
                executionTime={backtest.execution_time}
              />
              <div className="flex gap-2">
                <button
                  onClick={() => openDownload(backtest.task_id, "download")}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-border
                             px-3 py-2 text-xs font-medium hover:bg-secondary transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  CSV
                </button>
                <button
                  onClick={() => openDownload(backtest.task_id, "tearsheet")}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-border
                             px-3 py-2 text-xs font-medium hover:bg-secondary transition-colors"
                >
                  <FileText className="w-3.5 h-3.5" />
                  Tearsheet
                </button>
              </div>
            </>
          )}

          {backtest.status === "failed" && backtest.error_message && (
            <div className="rounded-md bg-red-50 border border-red-200 p-3">
              <p className="text-xs text-red-700 break-words">
                {backtest.error_message.length > 500
                  ? backtest.error_message.slice(0, 500) + "…"
                  : backtest.error_message}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
