import { useState } from "react"
import { createPortal } from "react-dom"
import { Globe, X, ChevronRight, Trash2 } from "lucide-react"
import { useUniverses, useUniverseSecurities, useDeleteUniverse } from "../../api/hooks"
import { CollapsibleSection } from "../ui/CollapsibleSection"
import type { UniverseItem } from "../../api/types"

function UniverseSecuritiesPanel({
  universe,
  onClose,
}: {
  universe: UniverseItem
  onClose: () => void
}) {
  const { data, isLoading } = useUniverseSecurities(universe.name)

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-card border border-border rounded-lg w-[520px] max-h-[80vh] flex flex-col shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div>
            <h2 className="font-semibold text-sm">{universe.name}</h2>
            <p className="text-xs text-muted-foreground">
              {universe.security_count} securities
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-secondary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 p-2">
          {isLoading ? (
            <p className="text-xs text-muted-foreground p-2">Loading...</p>
          ) : !data || data.securities.length === 0 ? (
            <p className="text-xs text-muted-foreground p-2">No securities found.</p>
          ) : (
            <>
              {data.total_count > 500 && (
                <p className="text-xs text-muted-foreground px-2 pb-2">
                  Showing first 500 of {data.total_count}
                </p>
              )}
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-muted-foreground">
                    <th className="text-left px-2 py-1 font-medium">Symbol</th>
                    <th className="text-left px-2 py-1 font-medium">Name</th>
                    <th className="text-left px-2 py-1 font-medium">Type</th>
                    <th className="text-left px-2 py-1 font-medium">Exchange</th>
                  </tr>
                </thead>
                <tbody>
                  {data.securities.map((sec) => (
                    <tr
                      key={sec.sid}
                      className="hover:bg-secondary/40 rounded transition-colors"
                    >
                      <td className="px-2 py-1 font-mono font-medium">{sec.symbol}</td>
                      <td className="px-2 py-1 text-muted-foreground truncate max-w-[180px]">
                        {sec.name ?? "—"}
                      </td>
                      <td className="px-2 py-1 text-muted-foreground">{sec.security_type ?? "—"}</td>
                      <td className="px-2 py-1 text-muted-foreground">{sec.exchange ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}

export function UniverseList() {
  const { data, isLoading } = useUniverses()
  const [selected, setSelected] = useState<UniverseItem | null>(null)
  const [deletingName, setDeletingName] = useState<string | null>(null)
  const deleteMutation = useDeleteUniverse()

  const universes = data?.universes ?? []

  const handleDelete = (e: React.MouseEvent, name: string) => {
    e.stopPropagation()
    setDeletingName(name)
    deleteMutation.mutate(name, { onSettled: () => setDeletingName(null) })
  }

  return (
    <>
      <CollapsibleSection
        title="Universes"
        icon={<Globe className="w-3.5 h-3.5 text-muted-foreground" />}
      >
        {isLoading ? (
          <p className="text-xs text-muted-foreground">Loading...</p>
        ) : universes.length === 0 ? (
          <p className="text-xs text-muted-foreground">No universes found.</p>
        ) : (
          <div className="space-y-1.5 max-h-[240px] overflow-y-auto">
            {universes.map((u) => (
              <div
                key={u.name}
                role="button"
                tabIndex={0}
                onClick={() => setSelected(u)}
                onKeyDown={(e) => e.key === "Enter" && setSelected(u)}
                className="group w-full text-left rounded-md border border-border p-2 hover:bg-secondary/50
                           transition-colors text-xs flex items-center justify-between cursor-pointer"
              >
                <span className="font-medium truncate">{u.name}</span>
                <div className="flex items-center gap-1.5 shrink-0 ml-2">
                  <span className="text-[10px] text-muted-foreground bg-secondary px-1.5 py-0.5 rounded-full">
                    {u.security_count}
                  </span>
                  <button
                    onClick={(e) => handleDelete(e, u.name)}
                    disabled={deletingName === u.name}
                    className="p-0.5 rounded hover:bg-destructive/20 transition-colors opacity-0 group-hover:opacity-100
                               disabled:opacity-30"
                    aria-label={`Delete ${u.name}`}
                  >
                    <Trash2 className="w-3 h-3 text-destructive" />
                  </button>
                  <ChevronRight className="w-3 h-3 text-muted-foreground" />
                </div>
              </div>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {selected && (
        <UniverseSecuritiesPanel
          universe={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  )
}
