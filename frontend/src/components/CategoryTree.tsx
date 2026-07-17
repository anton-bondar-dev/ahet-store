import type { CategoryNode } from '../lib/categoryTree'

type Props = {
  nodes: CategoryNode[]
  selectedId: number | null
  expanded: Set<number>
  counts: Map<number, number>
  onSelect: (id: number) => void
  onToggle: (id: number) => void
  depth?: number
}

// Recursive accordion: each node can be expanded to reveal its children, and
// selected to filter the catalog (the API cascades to the whole subtree).
export function CategoryTree({
  nodes,
  selectedId,
  expanded,
  counts,
  onSelect,
  onToggle,
  depth = 0,
}: Props) {
  return (
    <ul className="flex flex-col gap-0.5">
      {nodes.map((node) => {
        const hasChildren = node.children.length > 0
        const isExpanded = expanded.has(node.id)
        const isActive = selectedId === node.id
        const count = counts.get(node.id) ?? 0

        return (
          <li key={node.id}>
            <div
              className={`flex items-center rounded-md border-l-2 transition ${
                isActive
                  ? 'border-brand bg-brand-light'
                  : 'border-transparent hover:bg-gray-50'
              }`}
              style={{ paddingLeft: `${depth * 14}px` }}
            >
              {/* Expand/collapse toggle (or a spacer to keep labels aligned) */}
              {hasChildren ? (
                <button
                  type="button"
                  onClick={() => onToggle(node.id)}
                  aria-label={isExpanded ? 'Згорнути' : 'Розгорнути'}
                  aria-expanded={isExpanded}
                  className="flex h-7 w-6 shrink-0 items-center justify-center text-gray-400 transition hover:text-gray-700"
                >
                  <svg
                    viewBox="0 0 20 20"
                    className={`h-3.5 w-3.5 transition-transform ${
                      isExpanded ? 'rotate-90' : ''
                    }`}
                    fill="currentColor"
                    aria-hidden="true"
                  >
                    <path d="M7 5l6 5-6 5z" />
                  </svg>
                </button>
              ) : (
                <span className="h-7 w-6 shrink-0" />
              )}

              <button
                type="button"
                onClick={() => onSelect(node.id)}
                className={`flex flex-1 items-center justify-between gap-2 rounded-md py-1.5 pr-2 text-left text-sm transition ${
                  isActive
                    ? 'font-semibold text-brand'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <span className="truncate">{node.name}</span>
                {count > 0 && (
                  <span className="ml-2 shrink-0 text-xs text-gray-400">
                    {count}
                  </span>
                )}
              </button>
            </div>

            {hasChildren && isExpanded && (
              <CategoryTree
                nodes={node.children}
                selectedId={selectedId}
                expanded={expanded}
                counts={counts}
                onSelect={onSelect}
                onToggle={onToggle}
                depth={depth + 1}
              />
            )}
          </li>
        )
      })}
    </ul>
  )
}
