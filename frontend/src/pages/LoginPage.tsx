import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  getLoginChallenge,
  verifyLoginChallenge,
} from '../api/generated/auth/auth'
import { GoogleSignInButton } from '../components/GoogleSignInButton'
import { useAuth } from '../hooks/useAuth'

type Pending = {
  method: string
  challengeId: string
  matchCode: number
}

export function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submitLogin = async () => {
    const result = await login(email, password)
    if (result.status === 'authed') {
      navigate('/')
    } else if (result.status === 'pending' && result.challenge_id) {
      setPending({
        method: result.method ?? 'telegram',
        challengeId: result.challenge_id,
        matchCode: result.match_code ?? 0,
      })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await submitLogin()
    } catch {
      setError('Невірний email або пароль')
    } finally {
      setBusy(false)
    }
  }

  if (pending?.method === 'email') {
    return (
      <EmailOtpScreen
        pending={pending}
        onResend={submitLogin}
        onCancel={() => setPending(null)}
      />
    )
  }

  if (pending) {
    return (
      <TelegramApprovalScreen
        pending={pending}
        onCancel={() => setPending(null)}
      />
    )
  }

  return (
    <div className="mx-auto max-w-md p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Вхід</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
          />
        </label>

        <div className="-mt-2 flex justify-end">
          <Link
            to="/forgot-password"
            className="text-xs font-medium text-gray-500 transition hover:text-brand"
          >
            Забули пароль?
          </Link>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
        >
          {busy ? 'Вхід…' : 'Увійти'}
        </button>
      </form>

      <OrDivider />
      <div className="flex justify-center">
        <GoogleSignInButton />
      </div>

      <p className="mt-4 text-sm text-gray-500">
        Немає акаунта?{' '}
        <Link to="/register" className="font-medium text-gray-900 hover:underline">
          Зареєструватися
        </Link>
      </p>
    </div>
  )
}

function OrDivider() {
  return (
    <div className="my-5 flex items-center gap-3 text-xs text-gray-400">
      <span className="h-px flex-1 bg-gray-200" />
      або
      <span className="h-px flex-1 bg-gray-200" />
    </div>
  )
}

function TelegramApprovalScreen({
  pending,
  onCancel,
}: {
  pending: Pending
  onCancel: () => void
}) {
  const navigate = useNavigate()
  const { applyAuthed } = useAuth()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const timer = setInterval(async () => {
      try {
        const res = await getLoginChallenge(pending.challengeId)
        if (!active) return
        if (res.data.status === 'authed') {
          clearInterval(timer)
          applyAuthed(res.data)
          navigate('/')
        }
      } catch {
        if (!active) return
        clearInterval(timer)
        setError('Запит відхилено або протерміновано. Спробуйте ще раз.')
      }
    }, 2000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [pending.challengeId, applyAuthed, navigate])

  return (
    <div className="mx-auto max-w-md p-6 text-center">
      <div className="rounded-2xl border border-gray-200 p-8">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 text-2xl">
          ✈️
        </div>
        <h1 className="text-xl font-bold text-gray-900">
          Підтвердіть вхід у Telegram
        </h1>
        <p className="mt-2 text-sm text-gray-500">
          Ми надіслали запит у ваш Telegram. Переконайтесь, що число збігається,
          і натисніть «Підтвердити».
        </p>

        <div className="my-6">
          <span className="inline-block rounded-xl bg-gray-100 px-6 py-3 text-4xl font-bold tracking-widest text-gray-900">
            {pending.matchCode}
          </span>
        </div>

        {error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : (
          <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-gray-700" />
            Очікування підтвердження…
          </div>
        )}

        <button
          type="button"
          onClick={onCancel}
          className="mt-6 text-sm font-medium text-gray-500 hover:text-gray-900"
        >
          Скасувати
        </button>
      </div>
    </div>
  )
}

function EmailOtpScreen({
  pending,
  onResend,
  onCancel,
}: {
  pending: Pending
  onResend: () => Promise<void>
  onCancel: () => void
}) {
  const navigate = useNavigate()
  const { applyAuthed } = useAuth()
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const res = await verifyLoginChallenge(pending.challengeId, { code })
      if (res.data.status === 'authed') {
        applyAuthed(res.data)
        navigate('/')
      }
    } catch {
      setError('Невірний або протермінований код')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md p-6 text-center">
      <div className="rounded-2xl border border-gray-200 p-8">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-gray-100 text-2xl">
          ✉️
        </div>
        <h1 className="text-xl font-bold text-gray-900">
          Введіть код підтвердження
        </h1>
        <p className="mt-2 text-sm text-gray-500">
          Ми надіслали 6-значний код на вашу електронну пошту. Введіть його нижче,
          щоб завершити вхід.
        </p>

        <form onSubmit={handleVerify} className="mt-6 flex flex-col items-center gap-4">
          <label className="text-xs font-medium text-gray-500" htmlFor="otp-input">
            Код з email
          </label>
          <input
            id="otp-input"
            autoFocus
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            pattern="[0-9]{6}"
            required
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            className="w-48 rounded-lg border border-gray-300 py-3 text-center text-2xl font-bold tracking-[0.4em] focus:border-gray-500 focus:outline-none"
            placeholder="______"
          />

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={busy || code.length < 6}
            className="w-full rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
          >
            {busy ? 'Перевірка…' : 'Підтвердити'}
          </button>
        </form>

        <div className="mt-6 flex items-center justify-center gap-4 text-sm text-gray-500">
          <button
            type="button"
            onClick={() => {
              setError(null)
              onResend().catch(() => setError('Не вдалося надіслати код'))
            }}
            className="font-medium hover:text-gray-900"
          >
            Надіслати код ще раз
          </button>
          <span>·</span>
          <button
            type="button"
            onClick={onCancel}
            className="font-medium hover:text-gray-900"
          >
            Скасувати
          </button>
        </div>
      </div>
    </div>
  )
}
