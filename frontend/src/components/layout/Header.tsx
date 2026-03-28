import { Menu, PanelLeft } from "lucide-react"

interface HeaderProps {
  onToggleChatSidebar: () => void
  onToggleSidebar: () => void
}

export function Header({ onToggleChatSidebar, onToggleSidebar }: HeaderProps) {
  return (
    <header className="h-14 border-b border-border bg-card flex items-center px-4 shrink-0">
      <button
        onClick={onToggleChatSidebar}
        className="md:hidden mr-2 p-1.5 rounded-md hover:bg-secondary"
      >
        <PanelLeft className="w-5 h-5" />
      </button>
      <h1 className="text-lg font-bold tracking-tight text-foreground">
        Quato
      </h1>
      <span className="ml-2 text-xs text-muted-foreground hidden sm:inline">
        AI Strategy Builder
      </span>
      <div className="ml-auto">
        <button
          onClick={onToggleSidebar}
          className="md:hidden p-1.5 rounded-md hover:bg-secondary"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>
    </header>
  )
}
