import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  getStaffListProductsQueryKey,
  useStaffListProducts,
  useStaffUpdateProduct,
} from '../../api/generated/catalog-admin/catalog-admin'
import { formatPrice } from '../../lib/format'

type SortKey = 'title' | 'price' | 'stock' | 'views_count' | 'purchases_count' | 'trending_score'
const LOW_STOCK = 5

const COLUMNS: { key: SortKey; label: string; align?: string }[] = [
  { key: 'title', label: 'Назва' },
  { key: 'price', label: 'Ціна' },
  { key: 'stock', label: 'Залишок' },
  { key: 'views_count', label: 'Перегляди' },
  { key: 'purchases_count', label: 'Продажі' },
  { key: 'trending_score', label: 'Популярність' },
]

// Internal product-management table: sortable, with quick inline edit of price
// and stock, plus staff-only 🔥/🧊 trending badges.
export function ProductsTab({ canEditPrice = false }: { canEditPrice?: boolean }) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useStaffListProducts()
  const update = useStaffUpdateProduct({
    mutation: {
      onSuccess: () =>
        queryClient.invalidateQueries({ queryKey: getStaffListProductsQueryKey() }),
    },
  })
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({
    key: 'trending_score',
    dir: 'desc',
  })

  const products = data?.data ?? []

  // 🔥/🧊 thresholds: top / bottom decile of the positive trending scores.
  const scores = products.map((p) => p.trending_score ?? 0).filter((s) => s > 0).sort((a, b) => a - b)
  const pct = (p: number) =>
    scores.length ? scores[Math.min(scores.length - 1, Math.floor(p * scores.length))] : Infinity
  const hot = scores.length >= 5 ? pct(0.9) : Infinity
  const cold = scores.length >= 5 ? pct(0.1) : -Infinity
  const badgeOf = (s: number): 'hot' | 'cold' | null =>
    s > 0 && s >= hot ? 'hot' : s > 0 && s <= cold ? 'cold' : null

  const sorted = [...products].sort((a, b) => {
    const dir = sort.dir === 'asc' ? 1 : -1
    if (sort.key === 'title') return dir * a.title.localeCompare(b.title)
    if (sort.key === 'price') return dir * (Number(a.price) - Number(b.price))
    return dir * (((a[sort.key] as number) ?? 0) - ((b[sort.key] as number) ?? 0))
  })

  const toggleSort = (key: SortKey) =>
    setSort((s) =>
      s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' },
    )

  const save = (id: number, patch: { price?: string; stock?: number }) =>
    update.mutate({ productId: id, data: patch })

  if (isLoading) return <p className="text-sm text-gray-400">Завантаження…</p>

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {products.length} товарів · клік по клітинці «{canEditPrice ? 'Ціна»/«Залишок' : 'Залишок'}» — швидке редагування
        </p>
        <button
          type="button"
          onClick={() => setSort({ key: 'trending_score', dir: 'desc' })}
          className="rounded-md bg-gray-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-gray-700"
        >
          🔥 Сортувати за популярністю
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              {COLUMNS.map((col) => (
                <th key={col.key} className="px-4 py-2">
                  <button type="button" onClick={() => toggleSort(col.key)} className="inline-flex items-center gap-1 hover:text-gray-900">
                    {col.label}
                    {sort.key === col.key && <span>{sort.dir === 'asc' ? '▲' : '▼'}</span>}
                  </button>
                </th>
              ))}
              <th className="px-4 py-2">Тренд</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sorted.map((p) => {
              const badge = badgeOf(p.trending_score ?? 0)
              return (
                <tr key={p.id} className={p.is_active ? '' : 'bg-gray-50 text-gray-400'}>
                  <td className="max-w-[16rem] truncate px-4 py-2 font-medium text-gray-900">{p.title}</td>
                  <td className="px-4 py-2">
                    {canEditPrice ? (
                      <EditCell
                        value={p.price}
                        display={formatPrice(p.price)}
                        onSave={(v) => save(p.id, { price: v })}
                      />
                    ) : (
                      <span className="text-gray-900">{formatPrice(p.price)}</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <EditCell
                      value={String(p.stock)}
                      display={
                        <span className={p.stock < LOW_STOCK ? 'font-semibold text-red-600' : 'text-gray-900'}>
                          {p.stock < LOW_STOCK && '⚠️ '}
                          {p.stock} шт
                        </span>
                      }
                      onSave={(v) => save(p.id, { stock: Math.max(0, parseInt(v, 10) || 0) })}
                    />
                  </td>
                  <td className="px-4 py-2 text-gray-600">{p.views_count}</td>
                  <td className="px-4 py-2 text-gray-600">{p.purchases_count}</td>
                  <td className="px-4 py-2 text-gray-600">{(p.trending_score ?? 0).toFixed(2)}</td>
                  <td className="px-4 py-2">
                    {badge === 'hot' && <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">🔥 Hot</span>}
                    {badge === 'cold' && <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-semibold text-sky-700">🧊 Cold</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function EditCell({
  value,
  display,
  onSave,
}: {
  value: string
  display: React.ReactNode
  onSave: (value: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])

  const commit = () => {
    setEditing(false)
    if (draft !== value && draft.trim() !== '') onSave(draft.trim())
    else setDraft(value)
  }

  if (editing) {
    return (
      <input
        autoFocus
        type="number"
        min={0}
        step="0.01"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit()
          if (e.key === 'Escape') { setDraft(value); setEditing(false) }
        }}
        className="w-24 rounded-md border border-gray-400 px-2 py-1 text-sm focus:outline-none"
      />
    )
  }
  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      className="rounded px-1 text-left transition hover:bg-gray-100"
      title="Редагувати"
    >
      {display}
    </button>
  )
}
