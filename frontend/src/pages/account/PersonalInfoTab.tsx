import { useEffect, useState } from 'react'
import { getProfile, updateProfile } from '../../api/generated/accounts/accounts'
import { useAuth } from '../../hooks/useAuth'

type Form = {
  username: string
  first_name: string
  last_name: string
  phone_number: string
  city: string
  delivery_address: string
}

const EMPTY: Form = {
  username: '',
  first_name: '',
  last_name: '',
  phone_number: '',
  city: '',
  delivery_address: '',
}

export function PersonalInfoTab({ nameOnly = false }: { nameOnly?: boolean }) {
  const { refreshUser } = useAuth()
  const [form, setForm] = useState<Form>(EMPTY)
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getProfile()
      .then((res) => {
        if (!active) return
        const d = res.data
        setForm({
          username: d.username,
          first_name: d.first_name,
          last_name: d.last_name,
          phone_number: d.phone_number,
          city: d.city,
          delivery_address: d.delivery_address,
        })
        setEmail(d.email)
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }))
    setSaved(false)
    setError(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await updateProfile(form)
      setSaved(true)
      await refreshUser() // header / review author names reflect the new username
    } catch {
      setError('Не вдалося зберегти. Можливо, це ім’я користувача вже зайняте.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="text-gray-500">Завантаження…</p>

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold text-gray-900">
        {nameOnly ? 'Ваше ім’я' : 'Особисті дані'}
      </h2>
      <p className="mb-5 text-sm text-gray-500">
        {nameOnly
          ? 'Ім’я, яке бачать колеги у робочому просторі підтримки.'
          : 'Ці дані автоматично підставляються під час оформлення замовлення.'}
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Ім'я" value={form.first_name} onChange={set('first_name')} />
          <Field label="Прізвище" value={form.last_name} onChange={set('last_name')} />
          {!nameOnly && (
            <>
              <Field
                label="Ім'я користувача (логін)"
                value={form.username}
                onChange={set('username')}
                required
              />
              <Field label="Email" value={email} disabled />
              <Field label="Телефон" value={form.phone_number} onChange={set('phone_number')} />
              <Field label="Місто" value={form.city} onChange={set('city')} />
              <Field
                label="Відділення пошти / Адреса"
                value={form.delivery_address}
                onChange={set('delivery_address')}
              />
            </>
          )}
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className="w-fit rounded-md bg-gray-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-700 disabled:opacity-60"
          >
            {saving ? 'Збереження…' : 'Зберегти'}
          </button>
          {saved && <span className="text-sm text-green-600">Збережено ✓</span>}
        </div>
      </form>
    </div>
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
        className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-gray-500 focus:outline-none disabled:bg-gray-50 disabled:text-gray-500"
      />
    </label>
  )
}
