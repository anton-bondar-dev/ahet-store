import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { confirmPasswordReset } from '../api/generated/auth/auth'
import { PasswordInput } from '../components/PasswordInput'
import { useAuth } from '../hooks/useAuth'
import { apiErrorMessage } from '../lib/apiError'
import { setTokens } from '../lib/authToken'

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const uid = params.get('uid') ?? ''
  const token = params.get('token') ?? ''
  const navigate = useNavigate()
  const { refreshUser } = useAuth()

  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const invalidLink = !uid || !token

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (next !== confirm) {
      setError('Паролі не збігаються.')
      return
    }
    if (next.length < 8) {
      setError('Пароль має містити щонайменше 8 символів.')
      return
    }
    setBusy(true)
    try {
      const res = await confirmPasswordReset({ uid, token, new_password: next })
      // The endpoint logs the user in — apply the tokens and load the user.
      setTokens(res.data.access, res.data.refresh)
      await refreshUser()
      navigate('/')
    } catch (err) {
      setError(
        apiErrorMessage(err) ??
          'Не вдалося змінити пароль. Посилання могло застаріти.',
      )
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Новий пароль</h1>
      {invalidLink ? (
        <div className="rounded-lg border border-gray-200 p-5 text-sm text-gray-700">
          <p>
            Посилання для відновлення недійсне або неповне.{' '}
            <Link
              to="/forgot-password"
              className="font-medium text-brand hover:underline"
            >
              Запросити нове
            </Link>
            .
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <p className="text-sm text-gray-500">Введіть новий пароль для акаунта.</p>
          <PasswordInput
            autoComplete="new-password"
            required
            value={next}
            onChange={(e) => setNext(e.target.value)}
            placeholder="Новий пароль"
          />
          <PasswordInput
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Повторіть новий пароль"
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
          >
            {busy ? 'Збереження…' : 'Встановити пароль'}
          </button>
        </form>
      )}
    </div>
  )
}
