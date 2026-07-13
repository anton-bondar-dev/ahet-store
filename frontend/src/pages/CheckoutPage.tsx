import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { getGetCartQueryKey } from '../api/generated/cart/cart'
import { useCheckout } from '../api/generated/orders/orders'
import { productImageUrl } from '../api/http'
import { useCart } from '../hooks/useCart'
import { effectivePrice, formatPrice } from '../lib/format'

type Form = {
  first_name: string
  last_name: string
  phone: string
  email: string
  city: string
  address: string
}

const EMPTY: Form = {
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  city: '',
  address: '',
}

export function CheckoutPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { items, totalQuantity, totalPrice } = useCart()
  const checkout = useCheckout()

  const [form, setForm] = useState<Form>(EMPTY)
  const [error, setError] = useState<string | null>(null)

  const activeItems = items.filter((item) => item.quantity > 0)

  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

  if (totalQuantity === 0) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <h1 className="mb-4 text-2xl font-bold text-gray-900">Оформлення замовлення</h1>
        <div className="rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-500">Кошик порожній.</p>
          <Link to="/" className="mt-4 inline-block text-sm font-medium text-gray-700 hover:text-gray-900">
            ← Повернутися до магазину
          </Link>
        </div>
      </div>
    )
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    checkout
      .mutateAsync({ data: form })
      .then((response) => {
        queryClient.invalidateQueries({ queryKey: getGetCartQueryKey() })
        navigate(`/order-success/${response.data.id}`)
      })
      .catch(() => {
        setError('Не вдалося оформити замовлення. Спробуйте ще раз.')
      })
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-6xl p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Оформлення замовлення</h1>

      <div className="grid gap-8 lg:grid-cols-3">
        {/* Left — form */}
        <div className="flex flex-col gap-8 lg:col-span-2">
          <fieldset className="rounded-lg border border-gray-200 p-5">
            <legend className="px-2 text-sm font-semibold text-gray-900">
              Контактна інформація
            </legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Ім'я" required value={form.first_name} onChange={set('first_name')} />
              <Field label="Прізвище" required value={form.last_name} onChange={set('last_name')} />
              <Field
                label="Телефон"
                type="tel"
                required
                pattern="^\+?[0-9\s\-()]{10,}$"
                placeholder="+380 XX XXX XX XX"
                value={form.phone}
                onChange={set('phone')}
              />
              <Field
                label="Email"
                type="email"
                required
                placeholder="you@example.com"
                value={form.email}
                onChange={set('email')}
              />
            </div>
          </fieldset>

          <fieldset className="rounded-lg border border-gray-200 p-5">
            <legend className="px-2 text-sm font-semibold text-gray-900">Доставка</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Місто" required value={form.city} onChange={set('city')} />
              <Field
                label="Відділення пошти / Адреса"
                required
                value={form.address}
                onChange={set('address')}
              />
            </div>
          </fieldset>
        </div>

        {/* Right — order summary */}
        <aside className="lg:col-span-1">
          <div className="sticky top-24 rounded-lg border border-gray-200 p-5">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">Ваше замовлення</h2>
            <ul className="mb-4 flex flex-col gap-3">
              {activeItems.map((item) => {
                const imageUrl = productImageUrl(item.product.image)
                return (
                  <li key={item.id} className="flex items-center gap-3">
                    <div className="h-12 w-12 shrink-0 overflow-hidden rounded border border-gray-200 bg-gray-50">
                      {imageUrl ? (
                        <img src={imageUrl} alt={item.product.title} className="h-full w-full object-cover" />
                      ) : null}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-1 text-sm text-gray-900">{item.product.title}</p>
                      <p className="text-xs text-gray-500">
                        {item.quantity} × {formatPrice(String(effectivePrice(item.product)))}
                      </p>
                    </div>
                    <span className="shrink-0 text-sm font-medium text-gray-900">
                      {formatPrice(String(effectivePrice(item.product) * item.quantity))}
                    </span>
                  </li>
                )
              })}
            </ul>

            <div className="mb-4 flex items-baseline justify-between border-t border-gray-100 pt-4">
              <span className="text-sm text-gray-500">Разом</span>
              <span className="text-xl font-bold text-gray-900">{formatPrice(totalPrice)}</span>
            </div>

            {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

            <button
              type="submit"
              disabled={checkout.isPending}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {checkout.isPending && (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              )}
              {checkout.isPending ? 'Обробка…' : 'Підтвердити замовлення'}
            </button>
          </div>
        </aside>
      </div>
    </form>
  )
}

function Field({
  label,
  ...props
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      <input
        {...props}
        className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-gray-500 focus:outline-none"
      />
    </label>
  )
}
