import { cn } from "../../lib/utils"

const statusConfig: Record<string, { label: string; className: string }> = {
  queued: { label: "Queued", className: "bg-yellow-100 text-yellow-800" },
  running: { label: "Running", className: "bg-blue-100 text-blue-800" },
  complete: { label: "Complete", className: "bg-green-100 text-green-800" },
  failed: { label: "Failed", className: "bg-red-100 text-red-800" },
}

interface BacktestStatusBadgeProps {
  status: string
}

export function BacktestStatusBadge({ status }: BacktestStatusBadgeProps) {
  const config = statusConfig[status] || { label: status, className: "bg-gray-100 text-gray-800" }
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium", config.className)}>
      {config.label}
    </span>
  )
}
