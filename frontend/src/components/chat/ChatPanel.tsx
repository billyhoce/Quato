import { useState, useCallback, useEffect } from "react"
import { MessageList } from "./MessageList"
import { ChatInput } from "./ChatInput"
import { useChat } from "../../api/hooks"
import { useSession } from "../../context/SessionContext"
import { apiFetch } from "../../api/client"
import type { ChatMessage, StrategySummaryResponse } from "../../api/types"

function loadMessages(sessionId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(`quato_messages_${sessionId}`)
    if (!raw) return []
    const parsed = JSON.parse(raw) as Array<Omit<ChatMessage, "timestamp"> & { timestamp: string }>
    return parsed.map((m) => ({ ...m, timestamp: new Date(m.timestamp) }))
  } catch {
    return []
  }
}

function saveMessages(sessionId: string, messages: ChatMessage[]) {
  localStorage.setItem(`quato_messages_${sessionId}`, JSON.stringify(messages))
}

interface ChatPanelProps {
  sessionId: string
  onStrategyUpdate: () => void
  pendingMessage?: { content: string; isSystem: boolean } | null
  onPendingMessageHandled?: () => void
  onPendingChange?: (isPending: boolean) => void
}

export function ChatPanel({
  sessionId,
  onStrategyUpdate,
  pendingMessage,
  onPendingMessageHandled,
  onPendingChange,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadMessages(sessionId))
  const chatMutation = useChat()
  const { autoRenameSession } = useSession()

  useEffect(() => {
    saveMessages(sessionId, messages)
  }, [messages, sessionId])

  useEffect(() => {
    onPendingChange?.(chatMutation.isPending)
  }, [chatMutation.isPending, onPendingChange])

  const handleSend = useCallback(
    (content: string, role: "user" | "system" = "user") => {
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role,
        content,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, userMsg])

      chatMutation.mutate(
        { message: content },
        {
          onSuccess: (data) => {
            const agentMsg: ChatMessage = {
              id: crypto.randomUUID(),
              role: "agent",
              content: data.message,
              timestamp: new Date(),
            }
            setMessages((prev) => [...prev, agentMsg])
            if (data.strategy_updated) {
              onStrategyUpdate()
              apiFetch<StrategySummaryResponse>("/strategy/summary")
                .then((res) => {
                  if (res.title) autoRenameSession(sessionId, res.title)
                })
                .catch(() => {})
            }
          },
          onError: (error) => {
            const errorMsg: ChatMessage = {
              id: crypto.randomUUID(),
              role: "agent",
              content: `Error: ${error.message}`,
              timestamp: new Date(),
            }
            setMessages((prev) => [...prev, errorMsg])
          },
        }
      )
    },
    [chatMutation, onStrategyUpdate, autoRenameSession, sessionId]
  )

  useEffect(() => {
    if (pendingMessage) {
      handleSend(pendingMessage.content, pendingMessage.isSystem ? "system" : "user")
      onPendingMessageHandled?.()
    }
  }, [pendingMessage]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="flex-1 flex flex-col min-w-0">
      <MessageList messages={messages} isLoading={chatMutation.isPending} />
      <ChatInput onSend={(content) => handleSend(content)} disabled={chatMutation.isPending} />
    </main>
  )
}
