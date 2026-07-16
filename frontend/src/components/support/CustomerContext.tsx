import { useTicketCustomerOrders } from '../../api/generated/support/support'
import { formatPrice } from '../../lib/format'

const ORDER_STATUS_LABELS: Record<string, string> = {
  new: 'Новий',
  processing: 'Обробка',
  shipped: 'Відправлено',
  delivered: 'Доставлено',
  cancelled: 'Скасовано',
}

// Recent orders of the ticket's author, shown beside the conversation so the
// agent has context without asking "what's your order number?".
export function CustomerContext({ ticketId }: { ticketId: number }) {
  const { data, isLoading } = useTicketCustomerOrders(ticketId)
  const orders = data?.data ?? []

  return (
    <aside className="rounded-lg border border-gray-200 p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Останні замовлення
      </p>
      {isLoading ? (
        <p className="text-sm text-gray-400">Завантаження…</p>
      ) : orders.length === 0 ? (
        <p className="text-sm text-gray-400">Замовлень немає</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {orders.map((o) => (
            <li key={o.id} className="rounded-md bg-gray-50 px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">№{o.id}</span>
                <span className="text-xs text-gray-500">
                  {ORDER_STATUS_LABELS[o.status] ?? o.status}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>{o.item_count} тов.</span>
                <span>{formatPrice(o.total_price)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
