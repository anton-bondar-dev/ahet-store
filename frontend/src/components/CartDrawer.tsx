import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import type { CartItemOut } from '../api/generated/onlineStoreAPI.schemas'
import { productImageUrl } from '../api/http'
import { useCartUI } from '../hooks/useCartUI'
import { useCart } from '../hooks/useCart'
import { effectivePrice, formatPrice } from '../lib/format'
import { QuantityStepper } from './QuantityStepper'

export function CartDrawer() {
  const { isDrawerOpen, closeDrawer } = useCartUI()
  const { items, totalQuantity, totalPrice, updateQuantity, removeItem } = useCart()

  // Escape closes as a convenience (X is the primary control).
  useEffect(() => {
    if (!isDrawerOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDrawer()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [isDrawerOpen, closeDrawer])

  return (
    // Non-modal side panel: no blocking overlay, so the rest of the store stays
    // interactive while the cart is open (browse + add items; the drawer updates
    // live via the shared cart cache). Closes only via the X button (or Escape).
    <aside
      aria-label="Кошик"
      className={`fixed right-0 top-0 z-[100] flex h-full w-full max-w-md flex-col border-l border-gray-200 bg-white shadow-xl transition-transform duration-300 ${
        isDrawerOpen ? 'translate-x-0' : 'pointer-events-none translate-x-full'
      }`}
    >
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Кошик</h2>
          <button
            type="button"
            onClick={closeDrawer}
            aria-label="Закрити"
            className="rounded p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-900"
          >
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="m5 5 10 10M15 5 5 15" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {items.length === 0 ? (
            <p className="p-5 text-sm text-gray-500">Кошик порожній.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {items.map((item) => (
                <CartDrawerItem
                  key={item.id}
                  item={item}
                  onQuantity={(q) => updateQuantity(item.id, q)}
                  onRemove={() => removeItem(item.id)}
                />
              ))}
            </ul>
          )}
        </div>

        <div className="border-t border-gray-200 p-5">
          <div className="mb-4 flex items-baseline justify-between">
            <span className="text-sm text-gray-500">Разом</span>
            <span className="text-lg font-bold text-gray-900">
              {formatPrice(totalPrice)}
            </span>
          </div>
          <Link
            to="/cart"
            onClick={closeDrawer}
            aria-disabled={totalQuantity === 0}
            className={`block rounded-md px-4 py-2.5 text-center text-sm font-semibold text-white transition ${
              totalQuantity === 0
                ? 'pointer-events-none bg-gray-300'
                : 'bg-gray-900 hover:bg-gray-700'
            }`}
          >
            Перейти до оформлення замовлення
          </Link>
        </div>
    </aside>
  )
}

function CartDrawerItem({
  item,
  onQuantity,
  onRemove,
}: {
  item: CartItemOut
  onQuantity: (quantity: number) => void
  onRemove: () => void
}) {
  const imageUrl = productImageUrl(item.product.image)
  const lineTotal = effectivePrice(item.product) * item.quantity
  const isZero = item.quantity === 0

  return (
    <li className={`flex gap-3 p-4 ${isZero ? 'opacity-50' : ''}`}>
      <div className="h-16 w-16 shrink-0 overflow-hidden rounded border border-gray-200 bg-gray-50">
        {imageUrl ? (
          <img src={imageUrl} alt={item.product.title} className="h-full w-full object-cover" />
        ) : null}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <p className="line-clamp-2 text-sm font-medium text-gray-900">
            {item.product.title}
          </p>
          <button
            type="button"
            onClick={onRemove}
            aria-label="Видалити товар"
            className="shrink-0 rounded p-1 text-gray-400 transition hover:bg-gray-100 hover:text-red-600"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="m5 5 10 10M15 5 5 15" />
            </svg>
          </button>
        </div>

        <div className="flex items-center justify-between gap-2">
          <QuantityStepper
            value={item.quantity}
            max={item.product.stock}
            onChange={onQuantity}
          />
          <span className="text-sm font-semibold text-gray-900">
            {formatPrice(String(lineTotal))}
          </span>
        </div>
      </div>
    </li>
  )
}
