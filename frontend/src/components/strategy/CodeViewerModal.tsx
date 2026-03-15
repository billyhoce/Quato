import { X, Copy, Check } from "lucide-react"
import { useState } from "react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism"

interface CodeViewerModalProps {
  open: boolean
  onClose: () => void
  code: string | null
}

export function CodeViewerModal({ open, onClose, code }: CodeViewerModalProps) {
  const [copied, setCopied] = useState(false)

  if (!open) return null

  const handleCopy = async () => {
    if (!code) return
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-card rounded-xl shadow-xl w-full max-w-3xl max-h-[80vh] mx-4 flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="font-semibold text-sm">Strategy Code</h2>
          <div className="flex items-center gap-1">
            <button
              onClick={handleCopy}
              className="p-1.5 rounded hover:bg-secondary text-muted-foreground"
              title="Copy code"
            >
              {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-secondary text-muted-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
        <div className="overflow-auto flex-1 p-4">
          {code ? (
            <SyntaxHighlighter
              language="python"
              style={oneLight}
              customStyle={{ margin: 0, borderRadius: "0.5rem", fontSize: "0.8rem" }}
              showLineNumbers
            >
              {code}
            </SyntaxHighlighter>
          ) : (
            <p className="text-sm text-muted-foreground">No strategy code available.</p>
          )}
        </div>
      </div>
    </div>
  )
}
