export interface ChatRequest {
  message: string
}

export interface ChatResponse {
  message: string
  strategy_updated: boolean
  strategy_code: string | null
  error: string | null
}

export interface StrategyResponse {
  code: string | null
  has_strategy: boolean
}

export interface StrategySummaryResponse {
  summary: string | null
  has_strategy: boolean
}

export interface BacktestRequest {
  bundle?: string
  start_date?: string
  end_date?: string
  capital_base?: number
}

export interface BacktestResponse {
  task_id: string
  status: string
  message: string
}

export interface BacktestResultResponse {
  task_id: string
  status: string
  success: boolean | null
  error_message: string | null
  csv_object_key: string | null
  total_return: number | null
  sharpe_ratio: number | null
  max_drawdown: number | null
  execution_time: number | null
}

export interface BacktestDownloadResponse {
  download_url: string
  expires_in: number
}

export interface BacktestHistoryResponse {
  backtests: BacktestHistoryItem[]
}

export interface BacktestHistoryItem {
  task_id: string
  status: string
  created_at: string
  completed_at: string | null
  success: boolean | null
  total_return: number | null
  sharpe_ratio: number | null
  max_drawdown: number | null
  execution_time: number | null
  error_message: string | null
}

export interface ChatMessage {
  id: string
  role: "user" | "agent"
  content: string
  timestamp: Date
}

export interface UniverseItem {
  name: string
  security_count: number
}

export interface UniverseListResponse {
  universes: UniverseItem[]
}

export interface SecurityItem {
  sid: string
  symbol: string
  name: string | null
  security_type: string | null
  exchange: string | null
}

export interface UniverseSecuritiesResponse {
  universe_name: string
  securities: SecurityItem[]
  total_count: number
}
