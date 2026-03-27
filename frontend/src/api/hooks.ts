import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "./client"
import type {
  ChatRequest,
  ChatResponse,
  StrategyResponse,
  StrategySummaryResponse,
  BacktestRequest,
  BacktestResponse,
  BacktestResultResponse,
  BacktestDownloadResponse,
  BacktestHistoryResponse,
  UniverseListResponse,
  UniverseSecuritiesResponse,
} from "./types"

export function useChat() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ChatRequest) =>
      apiFetch<ChatResponse>("/chat", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: (data) => {
      if (data.strategy_updated) {
        queryClient.invalidateQueries({ queryKey: ["strategy"] })
        queryClient.invalidateQueries({ queryKey: ["strategySummary"] })
      }
    },
  })
}

export function useStrategy(enabled: boolean) {
  return useQuery({
    queryKey: ["strategy"],
    queryFn: () => apiFetch<StrategyResponse>("/strategy/current"),
    enabled,
  })
}

export function useStrategySummary(enabled: boolean) {
  return useQuery({
    queryKey: ["strategySummary"],
    queryFn: () => apiFetch<StrategySummaryResponse>("/strategy/summary"),
    enabled,
  })
}

export function useStartBacktest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: BacktestRequest) =>
      apiFetch<BacktestResponse>("/backtest", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtestHistory"] })
    },
  })
}

export function useBacktestStatus(taskId: string | null) {
  return useQuery({
    queryKey: ["backtest", taskId],
    queryFn: () => apiFetch<BacktestResultResponse>(`/backtest/${taskId}`),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === "complete" || status === "failed") return false
      return 3000
    },
  })
}

export function useBacktestHistory() {
  return useQuery({
    queryKey: ["backtestHistory"],
    queryFn: () => apiFetch<BacktestHistoryResponse>("/backtest/history"),
  })
}

export function useBacktestDownload(taskId: string) {
  return useQuery({
    queryKey: ["backtestDownload", taskId],
    queryFn: () => apiFetch<BacktestDownloadResponse>(`/backtest/${taskId}/download`),
    enabled: false,
  })
}

export function useTearsheet(taskId: string) {
  return useQuery({
    queryKey: ["tearsheet", taskId],
    queryFn: () => apiFetch<BacktestDownloadResponse>(`/backtest/${taskId}/tearsheet`),
    enabled: false,
  })
}

export function useUniverses() {
  return useQuery({
    queryKey: ["universes"],
    queryFn: () => apiFetch<UniverseListResponse>("/universes"),
    staleTime: 60_000,
  })
}

export function useUniverseSecurities(name: string | null) {
  return useQuery({
    queryKey: ["universe-securities", name],
    queryFn: () => apiFetch<UniverseSecuritiesResponse>(`/universes/${name}/securities`),
    enabled: !!name,
    staleTime: 60_000,
  })
}
