import { Link, Navigate } from 'react-router-dom'
import { productImageUrl } from '../api/http'
import { useCart } from '../hooks/useCart'
import { useIsStaff } from '../hooks/useIsStaff'
import { effectivePrice, formatPrice } from '../lib/format'
import { QuantityStepper } from '../components/QuantityStepper'

export function CartPage() {
  const isStaff = useIsStaff()
  const { items, totalQuantity, totalPrice, updateQuantity, removeItem } = useCart()

  // Staff have no cart — bounce them back to the catalog.
  if (isStaff) return <Navigate to="/" replace />

  // Items set to 0 (in the drawer or here) are filtered out — setting one to 0
  // on this page makes it disappear immediately once the cache updates.
  const activeItems = items.filter((item) => item.quantity > 0)

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Кошик</h1>

      {activeItems.length === 0 ? (
        <div className="rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-500">Кошик порожній.</p>
          <Link
            to="/"
            className="mt-4 inline-block text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            ← Повернутися до магазину
          </Link>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-200 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Товар</th>
                  <th className="px-4 py-3 font-medium">Ціна</th>
                  <th className="px-4 py-3 font-medium">Кількість</th>
                  <th className="px-4 py-3 text-right font-medium">Сума</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {activeItems.map((item) => {
                  const unit = effectivePrice(item.product)
                  const imageUrl = productImageUrl(item.product.image)
                  return (
                    <tr key={item.id}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="h-12 w-12 shrink-0 overflow-hidden rounded border border-gray-200 bg-gray-50">
                            {imageUrl ? (
                              <img
                                src={imageUrl}
                                alt={item.product.title}
                                className="h-full w-full object-cover"
                              />
                            ) : null}
                          </div>
                          <Link
                            to={`/product/${item.product.slug}`}
                            className="line-clamp-2 max-w-xs font-medium text-gray-900 hover:text-gray-600"
                          >
                            {item.product.title}
                          </Link>
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-gray-600">
                        {formatPrice(String(unit))}
                      </td>
                      <td className="px-4 py-3">
                        <QuantityStepper
                          value={item.quantity}
                          max={item.product.stock}
                          onChange={(q) => updateQuantity(item.id, q)}
                        />
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-right font-semibold text-gray-900">
                        {formatPrice(String(unit * item.quantity))}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => removeItem(item.id)}
                          aria-label="Видалити товар"
                          className="rounded p-1 text-gray-400 transition hover:bg-gray-100 hover:text-red-600"
                        >
                          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                            <path d="m5 5 10 10M15 5 5 15" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-6 flex flex-col items-end gap-4">
            <div className="flex items-baseline gap-3">
              <span className="text-sm text-gray-500">Разом ({totalQuantity})</span>
              <span className="text-2xl font-bold text-gray-900">
                {formatPrice(totalPrice)}
              </span>
            </div>
            <Link
              to="/checkout"
              className="rounded-md bg-gray-900 px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-700"
            >
              Оформити замовлення
            </Link>
          </div>
        </>
      )}
    </div>
  )
}
