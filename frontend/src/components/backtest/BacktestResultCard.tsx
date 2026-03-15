import { TrendingUp, TrendingDown, BarChart3, Clock } from "lucide-react"
import { formatPercent, formatNumber, formatDuration } from "../../lib/utils"

interface BacktestResultCardProps {
  totalReturn: number | null
  sharpeRatio: number | null
  maxDrawdown: number | null
  executionTime: number | null
}

export function BacktestResultCard({ totalReturn, sharpeRatio, maxDrawdown, executionTime }: BacktestResultCardProps) {
  const metrics = [
    {
      label: "Total Return",
      value: formatPercent(totalReturn),
      icon: totalReturn != null && totalReturn >= 0 ? TrendingUp : TrendingDown,
      color: totalReturn != null && totalReturn >= 0 ? "text-green-600" : "text-red-600",
    },
    {
      label: "Sharpe Ratio",
      value: formatNumber(sharpeRatio),
      icon: BarChart3,
      color: "text-foreground",
    },
    {
      label: "Max Drawdown",
      value: formatPercent(maxDrawdown),
      icon: TrendingDown,
      color: "text-red-600",
    },
    {
      label: "Duration",
      value: formatDuration(executionTime),
      icon: Clock,
      color: "text-muted-foreground",
    },
  ]

  return (
    <div className="grid grid-cols-2 gap-2">
      {metrics.map((m) => (
        <div key={m.label} className="rounded-md border border-border p-2">
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-0.5">
            <m.icon className="w-3 h-3" />
            {m.label}
          </div>
          <div className={`text-sm font-semibold ${m.color}`}>{m.value}</div>
        </div>
      ))}
    </div>
  )
}
