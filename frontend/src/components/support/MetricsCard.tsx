import { useMySupportMetrics } from '../../api/generated/support/support'

// The logged-in staff member's own (private) performance snapshot. Scores are
// never shown to customers — only here and to superusers in the Django admin.
export function MetricsCard() {
  const { data } = useMySupportMetrics()
  const m = data?.data
  if (!m) return null

  const rate = m.positive_rate == null ? '—' : `${m.positive_rate}%`

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Stat label="Закрито звернень" value={m.resolved_tickets} />
      <Stat label="Вирішено коментарів" value={m.comments_resolved} />
      <Stat
        label="Позитивних оцінок"
        value={rate}
        hint={m.ratings_total ? `${m.ratings_positive}/${m.ratings_total}` : 'ще немає оцінок'}
      />
      <Stat label="Всього оцінок" value={m.ratings_total} />
    </div>
  )
}

function Stat({ label, value, hint }: { label: string; value: number | string; hint?: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
      {hint && <p className="text-[11px] text-gray-400">{hint}</p>}
    </div>
  )
}
