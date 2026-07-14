import { useGetMyOrders } from '../../api/generated/orders/orders'
import type { OrderOut } from '../../api/generated/onlineStoreAPI.schemas'
import { formatPrice } from '../../lib/format'
import { StatusStepper } from './StatusStepper'

export function OrdersTab() {
  const { data, isLoading, isError } = useGetMyOrders()
  const orders = data?.data ?? []

  if (isLoading) return <p className="text-gray-500">Завантаження…</p>
  if (isError) return <p className="text-red-600">Не вдалося завантажити замовлення.</p>

  if (orders.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center">
        <p className="text-gray-500">У вас ще немає замовлень.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold text-gray-900">Мої замовлення</h2>
      {orders.map((order) => (
        <OrderCard key={order.id} order={order} />
      ))}
    </div>
  )
}

function OrderCard({ order }: { order: OrderOut }) {
  const date = new Date(order.created_at).toLocaleDateString('uk-UA', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  })

  return (
    <div className="rounded-lg border border-gray-200 p-5">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="font-semibold text-gray-900">Замовлення №{order.id}</p>
          <p className="text-xs text-gray-500">{date}</p>
        </div>
        <div className="text-right">
          <p className="text-lg font-bold text-gray-900">
            {formatPrice(order.total_price)}
          </p>
          {order.bonus_earned > 0 && (
            <p className="text-xs font-medium text-amber-600">
              +{order.bonus_earned} бонусів
            </p>
          )}
        </div>
      </div>

      <ul className="mb-5 flex flex-col gap-1 text-sm text-gray-600">
        {order.items.map((item, i) => (
          <li key={i} className="flex justify-between gap-3">
            <span className="line-clamp-1">{item.product_title}</span>
            <span className="shrink-0 text-gray-400">
              {item.quantity} × {formatPrice(item.price)}
            </span>
          </li>
        ))}
      </ul>

      <StatusStepper status={order.status} />
    </div>
  )
}
