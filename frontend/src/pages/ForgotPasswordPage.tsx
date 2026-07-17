import { useState } from 'react'
import { Link } from 'react-router-dom'
import { requestPasswordReset } from '../api/generated/auth/auth'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await requestPasswordReset({ email })
    } catch {
      // Always show the same neutral message (never reveal if the email exists).
    }
    setSent(true)
    setBusy(false)
  }

  return (
    <div className="mx-auto max-w-md p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Відновлення пароля</h1>
      {sent ? (
        <div className="rounded-lg border border-gray-200 p-5 text-sm text-gray-700">
          <p>
            Якщо акаунт із такою адресою існує, ми надіслали на неї лист із
            посиланням для встановлення нового пароля.
          </p>
          <p className="mt-4">
            <Link to="/login" className="font-medium text-brand hover:underline">
              ← Повернутися до входу
            </Link>
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <p className="text-sm text-gray-500">
            Вкажіть email вашого акаунта — ми надішлемо посилання для встановлення
            нового пароля.
          </p>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-gray-500">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
          >
            {busy ? 'Надсилання…' : 'Надіслати посилання'}
          </button>
          <Link to="/login" className="text-sm text-gray-500 hover:text-gray-900">
            ← Повернутися до входу
          </Link>
        </form>
      )}
    </div>
  )
}
