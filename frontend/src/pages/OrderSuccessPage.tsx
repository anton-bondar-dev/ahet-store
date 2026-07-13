import { Link, useParams } from 'react-router-dom'
import { useGetOrder } from '../api/generated/orders/orders'
import { formatPrice } from '../lib/format'

export function OrderSuccessPage() {
  const { id } = useParams<{ id: string }>()
  const orderId = Number(id)
  const { data } = useGetOrder(orderId, {
    query: { enabled: Number.isFinite(orderId) },
  })
  const order = data?.data

  return (
    <div className="mx-auto max-w-lg p-6">
      <div className="mt-10 rounded-2xl border border-gray-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
          <svg className="h-8 w-8 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6 9 17l-5-5" />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-gray-900">Дякуємо за замовлення!</h1>
        <p className="mt-2 text-gray-600">
          Ваш номер замовлення:{' '}
          <span className="font-semibold text-gray-900">#{id}</span>
        </p>

        {order && (
          <div className="mt-6 rounded-lg bg-gray-50 p-4 text-left text-sm">
            <div className="flex justify-between py-1">
              <span className="text-gray-500">Сума</span>
              <span className="font-semibold text-gray-900">
                {formatPrice(order.total_price)}
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-gray-500">Статус</span>
              <span className="text-gray-900">В обробці</span>
            </div>
          </div>
        )}

        <p className="mt-6 text-sm text-gray-500">
          Ми зв'яжемося з вами найближчим часом для підтвердження.
        </p>

        <Link
          to="/"
          className="mt-6 inline-block rounded-md bg-gray-900 px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-700"
        >
          Продовжити покупки
        </Link>
      </div>
    </div>
  )
}
