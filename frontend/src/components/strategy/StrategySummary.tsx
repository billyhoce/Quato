import { Code2, Loader2 } from "lucide-react"
import { useStrategySummary } from "../../api/hooks"

interface StrategySummaryProps {
  hasStrategy: boolean
  onViewCode: () => void
}

export function StrategySummary({ hasStrategy, onViewCode }: StrategySummaryProps) {
  const { data, isLoading } = useStrategySummary(hasStrategy)

  if (!hasStrategy) {
    return (
      <div className="rounded-lg border border-border p-4">
        <h3 className="text-sm font-semibold mb-1">Strategy</h3>
        <p className="text-xs text-muted-foreground">
          No strategy yet. Start chatting to generate one.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <h3 className="text-sm font-semibold">Strategy</h3>
      {isLoading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="w-3 h-3 animate-spin" />
          Generating summary...
        </div>
      ) : (
        <p className="text-xs text-muted-foreground leading-relaxed">
          {data?.summary || "Summary unavailable."}
        </p>
      )}
      <button
        onClick={onViewCode}
        className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
      >
        <Code2 className="w-3.5 h-3.5" />
        View Code
      </button>
    </div>
  )
}
