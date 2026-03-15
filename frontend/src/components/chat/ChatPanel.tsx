import { useState, useCallback } from "react"
import { MessageList } from "./MessageList"
import { ChatInput } from "./ChatInput"
import { useChat } from "../../api/hooks"
import type { ChatMessage } from "../../api/types"

interface ChatPanelProps {
  onStrategyUpdate: () => void
}

export function ChatPanel({ onStrategyUpdate }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const chatMutation = useChat()

  const handleSend = useCallback(
    (content: string) => {
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
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
    [chatMutation, onStrategyUpdate]
  )

  return (
    <main className="flex-1 flex flex-col min-w-0">
      <MessageList messages={messages} isLoading={chatMutation.isPending} />
      <ChatInput onSend={handleSend} disabled={chatMutation.isPending} />
    </main>
  )
}
