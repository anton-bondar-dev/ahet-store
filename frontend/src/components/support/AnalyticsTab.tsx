import {
  useLeadAnalytics,
  useOperatorAnalytics,
} from '../../api/generated/analytics/analytics'
import { formatPrice } from '../../lib/format'

// The Team Lead sees full financials + low-stock; Operators see only their own
// KPIs and a trending-products cheat sheet (no revenue — least privilege).
export function AnalyticsTab({ isOwner }: { isOwner: boolean }) {
  return isOwner ? <LeadDashboard /> : <OperatorDashboard />
}

function Stat({ label, value, hint, danger }: { label: string; value: string | number; hint?: string; danger?: boolean }) {
  return (
    <div className={`rounded-lg border px-4 py-3 ${danger ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-white'}`}>
      <p className={`text-2xl font-bold ${danger ? 'text-red-700' : 'text-gray-900'}`}>{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
      {hint && <p className="text-[11px] text-gray-400">{hint}</p>}
    </div>
  )
}

function LeadDashboard() {
  const { data, isLoading } = useLeadAnalytics({ query: { refetchInterval: 30000 } })
  const d = data?.data
  if (isLoading || !d) return <p className="text-sm text-gray-400">Завантаження…</p>

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Дохід (всього)" value={formatPrice(d.total_revenue)} />
        <Stat label="Дохід (цей місяць)" value={formatPrice(d.month_revenue)} />
        <Stat label="Середній чек" value={formatPrice(d.average_order_value)} />
        <Stat label="Замовлень" value={d.orders_count} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Top products */}
        <div className="rounded-lg border border-gray-200 p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-900">Топ-5 продажів</h3>
          {d.top_products.length === 0 ? (
            <p className="text-sm text-gray-400">Ще немає продажів</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {d.top_products.map((p) => (
                <li key={p.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="truncate text-gray-900">{p.title}</span>
                  <span className="shrink-0 text-gray-500">
                    {p.quantity_sold} шт · {formatPrice(p.revenue)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* SLA */}
        <div className="rounded-lg border border-gray-200 p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-900">Підтримка (SLA)</h3>
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Відкрито" value={d.sla.open_tickets} />
            <Stat label="Закрито" value={d.sla.closed_tickets} />
            <Stat label="Прострочено 🚨" value={d.sla.overdue_tickets} danger={d.sla.overdue_tickets > 0} />
            <Stat label="Задоволеність" value={d.sla.satisfaction_rate == null ? '—' : `${d.sla.satisfaction_rate}%`} />
          </div>
        </div>
      </div>

      {/* Low stock */}
      <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-4">
        <h3 className="mb-3 text-sm font-semibold text-amber-800">⚠️ Замало на складі (&lt; 5)</h3>
        {d.low_stock.length === 0 ? (
          <p className="text-sm text-gray-500">Усі товари в достатку 🎉</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {d.low_stock.map((p) => (
              <li key={p.id} className="rounded-md bg-white px-3 py-1.5 text-sm ring-1 ring-amber-200">
                {p.title} · <span className="font-semibold text-red-600">{p.stock} шт</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function OperatorDashboard() {
  const { data, isLoading } = useOperatorAnalytics({ query: { refetchInterval: 30000 } })
  const d = data?.data
  if (isLoading || !d) return <p className="text-sm text-gray-400">Завантаження…</p>

  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-900">Мої показники</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Закрито звернень" value={d.closed_tickets} />
          <Stat label="Вирішено коментарів" value={d.comments_resolved} />
          <Stat label="Сер. час вирішення" value={d.avg_resolution_hours == null ? '—' : `${d.avg_resolution_hours} год`} />
          <Stat label="Задоволеність" value={d.satisfaction_rate == null ? '—' : `${d.satisfaction_rate}%`} />
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 p-4">
        <h3 className="mb-1 text-sm font-semibold text-gray-900">🔥 Що зараз в тренді</h3>
        <p className="mb-3 text-xs text-gray-500">Шпаргалка для продажів — рекомендуйте ці товари.</p>
        <ol className="space-y-2">
          {d.trending_products.map((p, i) => (
            <li key={p.id} className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2 text-sm">
              <span className="min-w-0 truncate text-gray-900">
                <span className="mr-1">{i === 0 ? '🔥' : `${i + 1}.`}</span>
                {p.title}
              </span>
              <span className="shrink-0 text-xs text-gray-400">
                👁 {p.views_count} · 🛒 {p.cart_adds_count} · ✅ {p.purchases_count}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}
