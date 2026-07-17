import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

// A breadcrumb crumb can be a route link (`to`), an in-page action (`onClick`,
// e.g. selecting a category in the catalog), a fully custom node, or a plain
// terminal label (the current page).
export type Crumb = {
  label: string
  to?: string
  onClick?: () => void
  node?: ReactNode
}

export function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="Навігаційний ланцюжок">
      <ol className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1
          return (
            <li key={index} className="flex min-w-0 items-center gap-2">
              {index > 0 && <span className="text-gray-300">/</span>}
              {crumb.node ? (
                crumb.node
              ) : crumb.to ? (
                <Link to={crumb.to} className="transition hover:text-gray-900">
                  {crumb.label}
                </Link>
              ) : crumb.onClick ? (
                <button
                  type="button"
                  onClick={crumb.onClick}
                  className="transition hover:text-gray-900"
                >
                  {crumb.label}
                </button>
              ) : (
                <span
                  className={`truncate ${isLast ? 'max-w-xs text-gray-700' : ''}`}
                  title={crumb.label}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {crumb.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
