import { useState } from "react"
import { Play, Loader2, Info } from "lucide-react"
import { CollapsibleSection } from "../ui/CollapsibleSection"

const BUNDLES = {
  "usstock-learn-1d": {
    label: "Daily — All US Stocks",
    description: "Daily price data for all US-listed stocks.",
    note: "Available date range: 2007–2011",
    minDate: "2007-01-01",
    maxDate: "2011-12-31",
    defaultStart: "2008-01-01",
    defaultEnd: "2011-12-31",
  },
  "usstock-free-1min": {
    label: "Minute — Select Stocks",
    description:
      "Minute price data for: Alcoa, Apple, Exxon Mobil, Home Depot, Johnson & Johnson, Krispy Kreme, Monsanto, Microsoft, SPDR S&P 500 ETF.",
    note: null,
    minDate: undefined,
    maxDate: undefined,
    defaultStart: "2008-01-01",
    defaultEnd: "2011-12-31",
  },
} as const

type BundleKey = keyof typeof BUNDLES

interface BacktestConfigFormProps {
  hasStrategy: boolean
  onRun: (config: { bundle: string; start_date: string; end_date: string; capital_base: number }) => void
  isRunning: boolean
}

export function BacktestConfigForm({ hasStrategy, onRun, isRunning }: BacktestConfigFormProps) {
  const [bundle, setBundle] = useState<BundleKey>("usstock-learn-1d")
  const [startDate, setStartDate] = useState<string>(BUNDLES["usstock-learn-1d"].defaultStart)
  const [endDate, setEndDate] = useState<string>(BUNDLES["usstock-learn-1d"].defaultEnd)
  const [capitalBase, setCapitalBase] = useState("100000")

  const bundleInfo = BUNDLES[bundle]

  const handleBundleChange = (newBundle: BundleKey) => {
    setBundle(newBundle)
    setStartDate(BUNDLES[newBundle].defaultStart)
    setEndDate(BUNDLES[newBundle].defaultEnd)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onRun({
      bundle,
      start_date: startDate,
      end_date: endDate,
      capital_base: parseFloat(capitalBase),
    })
  }

  return (
    <CollapsibleSection title="Backtest">
      <form onSubmit={handleSubmit} className="space-y-2">
        <label className="block">
          <span className="text-xs text-muted-foreground">Data Bundle</span>
          <select
            value={bundle}
            onChange={(e) => handleBundleChange(e.target.value as BundleKey)}
            className="mt-0.5 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {(Object.keys(BUNDLES) as BundleKey[]).map((key) => (
              <option key={key} value={key}>
                {BUNDLES[key].label}
              </option>
            ))}
          </select>
        </label>

        <div className="flex gap-1.5 rounded-md border border-border bg-muted/40 px-2.5 py-2 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <div>
            <p>{bundleInfo.description}</p>
            {bundleInfo.note && <p className="mt-0.5 font-medium">{bundleInfo.note}</p>}
          </div>
        </div>

        <label className="block">
          <span className="text-xs text-muted-foreground">Start Date</span>
          <input
            type="date"
            value={startDate}
            min={bundleInfo.minDate}
            max={bundleInfo.maxDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="mt-0.5 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="block">
          <span className="text-xs text-muted-foreground">End Date</span>
          <input
            type="date"
            value={endDate}
            min={bundleInfo.minDate}
            max={bundleInfo.maxDate}
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
    </CollapsibleSection>
  )
}
