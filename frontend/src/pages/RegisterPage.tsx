import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { GoogleSignInButton } from '../components/GoogleSignInButton'
import { useAuth } from '../hooks/useAuth'

export function RegisterPage() {
  const navigate = useNavigate()
  const { register } = useAuth()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const result = await register(name, email, password)
      if (result.status === 'authed') navigate('/')
    } catch {
      setError('Не вдалося зареєструватися. Можливо, акаунт із таким email вже існує.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Реєстрація</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-500">Ім'я</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-500">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-500">Пароль</span>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-700 disabled:opacity-60"
        >
          {busy ? 'Реєстрація…' : 'Зареєструватися'}
        </button>
      </form>

      <div className="my-5 flex items-center gap-3 text-xs text-gray-400">
        <span className="h-px flex-1 bg-gray-200" />
        або
        <span className="h-px flex-1 bg-gray-200" />
      </div>
      <div className="flex justify-center">
        <GoogleSignInButton />
      </div>

      <p className="mt-4 text-sm text-gray-500">
        Вже маєте акаунт?{' '}
        <Link to="/login" className="font-medium text-gray-900 hover:underline">
          Увійти
        </Link>
      </p>
    </div>
  )
}
