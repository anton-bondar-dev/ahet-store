import type { CategoryOut } from '../api/generated/onlineStoreAPI.schemas'

export type CategoryNode = CategoryOut & { children: CategoryNode[] }

// Build a nested tree from the flat, path-ordered category list the API returns.
// Because the API orders by materialized `path` (parents before descendants),
// children preserve their natural order.
export function buildCategoryTree(categories: CategoryOut[]): CategoryNode[] {
  const byId = new Map<number, CategoryNode>()
  for (const cat of categories) byId.set(cat.id, { ...cat, children: [] })

  const roots: CategoryNode[] = []
  for (const cat of categories) {
    const node = byId.get(cat.id)!
    const parent = cat.parent_id != null ? byId.get(cat.parent_id) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  return roots
}

// Subtree product counts: every product counts toward its own category and each
// of its ancestors, so a parent row shows the total available beneath it.
export function subtreeCounts(
  products: { category: CategoryOut }[],
): Map<number, number> {
  const counts = new Map<number, number>()
  const bump = (id: number) => counts.set(id, (counts.get(id) ?? 0) + 1)
  for (const product of products) {
    bump(product.category.id)
    for (const ancestor of product.category.ancestors ?? []) bump(ancestor.id)
  }
  return counts
}
