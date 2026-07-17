import { useEffect, useRef, useState } from 'react'
import {
  changePassword,
  logoutOtherSessions,
  set2faMethod,
  telegramLinkStart,
  telegramLinkStatus,
} from '../../api/generated/auth/auth'
import { PasswordInput } from '../../components/PasswordInput'
import { useAuth } from '../../hooks/useAuth'
import { apiErrorMessage } from '../../lib/apiError'
import { setTokens } from '../../lib/authToken'

type Method = 'none' | 'telegram' | 'email'

export function SecurityTab() {
  const { user, refreshUser } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [linkingTelegram, setLinkingTelegram] = useState(false)
  const [sessionMsg, setSessionMsg] = useState<string | null>(null)
  const [endingSessions, setEndingSessions] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const endOtherSessions = async () => {
    setSessionMsg(null)
    setEndingSessions(true)
    try {
      const res = await logoutOtherSessions()
      // Swap this session onto fresh tokens; all other devices are now logged out.
      setTokens(res.data.access, res.data.refresh)
      setSessionMsg('Усі інші сеанси завершено ✓')
    } catch {
      setSessionMsg('Не вдалося завершити сеанси')
    } finally {
      setEndingSessions(false)
    }
  }

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  if (!user) return null

  const current = (user.preferred_2fa_method ?? 'none') as Method
  const telegramLinked = !!user.telegram_linked

  const applyMethod = async (method: Method) => {
    setError(null)
    setBusy(true)
    try {
      await set2faMethod({ method })
      await refreshUser()
    } catch {
      setError('Не вдалося змінити метод.')
    } finally {
      setBusy(false)
    }
  }

  // Telegram needs a linked chat first: open the deep link, poll until bound,
  // then the bot itself sets the method to telegram (we just refresh).
  const chooseTelegram = async () => {
    if (telegramLinked) {
      applyMethod('telegram')
      return
    }
    setError(null)
    setLinkingTelegram(true)
    try {
      const res = await telegramLinkStart()
      window.open(res.data.url, '_blank', 'noopener')
      pollRef.current = setInterval(async () => {
        const status = await telegramLinkStatus()
        if (status.data.linked) {
          if (pollRef.current) clearInterval(pollRef.current)
          setLinkingTelegram(false)
          await refreshUser()
        }
      }, 3000)
    } catch {
      setLinkingTelegram(false)
      setError('Не вдалося почати підключення Telegram.')
    }
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900">Безпека & 2FA</h2>
      <p className="mt-1 text-sm text-gray-500">
        Оберіть, як підтверджувати вхід у ваш акаунт.
      </p>

      <div className="mt-5 flex flex-col gap-3">
        <MethodOption
          active={current === 'none'}
          title="Без 2FA"
          description="Вхід лише за паролем."
          disabled={busy}
          onSelect={() => applyMethod('none')}
        />
        <MethodOption
          active={current === 'telegram'}
          title="Telegram"
          description={
            telegramLinked
              ? 'Підтвердження одним дотиком у Telegram.'
              : 'Потрібно підключити Telegram (відкриється бот).'
          }
          disabled={busy || linkingTelegram}
          onSelect={chooseTelegram}
          note={linkingTelegram ? 'Очікування підключення…' : undefined}
        />
        <MethodOption
          active={current === 'email'}
          title="Email"
          description={`6-значний код на ${user.email}.`}
          disabled={busy}
          onSelect={() => applyMethod('email')}
        />
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {/* Change password */}
      <div className="mt-8 border-t border-gray-100 pt-5">
        <ChangePasswordForm />
      </div>

      {/* Log out of every other device */}
      <div className="mt-8 border-t border-gray-100 pt-5">
        <h3 className="text-sm font-semibold text-gray-900">Активні сеанси</h3>
        <p className="mt-1 text-sm text-gray-500">
          Вийти з акаунта на всіх інших пристроях (цей залишиться активним).
        </p>
        <button
          type="button"
          onClick={endOtherSessions}
          disabled={endingSessions}
          className="mt-3 rounded-md border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 disabled:opacity-60"
        >
          {endingSessions ? 'Завершення…' : 'Завершити всі інші сеанси'}
        </button>
        {sessionMsg && <span className="ml-3 text-sm text-green-600">{sessionMsg}</span>}
      </div>
    </div>
  )
}

function ChangePasswordForm() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setMsg(null)
    if (next !== confirm) {
      setMsg({ ok: false, text: 'Нові паролі не збігаються.' })
      return
    }
    if (next.length < 8) {
      setMsg({ ok: false, text: 'Пароль має містити щонайменше 8 символів.' })
      return
    }
    setBusy(true)
    try {
      const res = await changePassword({
        current_password: current,
        new_password: next,
      })
      // Password change rotates the security stamp (other devices are logged
      // out), so swap this session onto the fresh tokens it returns.
      setTokens(res.data.access, res.data.refresh)
      setMsg({ ok: true, text: 'Пароль змінено ✓ Інші сеанси завершено.' })
      setCurrent('')
      setNext('')
      setConfirm('')
    } catch (err) {
      setMsg({ ok: false, text: apiErrorMessage(err) ?? 'Не вдалося змінити пароль.' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-900">Зміна пароля</h3>
      <p className="mt-1 text-sm text-gray-500">
        Після зміни пароля всі інші сеанси буде завершено.
      </p>
      <form onSubmit={submit} className="mt-3 flex max-w-sm flex-col gap-3">
        <PasswordInput
          autoComplete="current-password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          placeholder="Поточний пароль"
        />
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
        <button
          type="submit"
          disabled={busy}
          className="w-fit rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
        >
          {busy ? 'Збереження…' : 'Змінити пароль'}
        </button>
        {msg && (
          <p className={`text-sm ${msg.ok ? 'text-green-600' : 'text-red-600'}`}>
            {msg.text}
          </p>
        )}
      </form>
    </div>
  )
}

function MethodOption({
  active,
  title,
  description,
  note,
  disabled,
  onSelect,
}: {
  active: boolean
  title: string
  description: string
  note?: string
  disabled?: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled || active}
      className={`flex items-center justify-between rounded-lg border p-4 text-left transition ${
        active
          ? 'border-gray-900 bg-gray-50'
          : 'border-gray-200 hover:border-gray-400 disabled:opacity-60'
      }`}
    >
      <div>
        <p className="text-sm font-medium text-gray-900">{title}</p>
        <p className="text-xs text-gray-500">{note ?? description}</p>
      </div>
      <span
        className={`ml-3 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
          active ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300'
        }`}
      >
        {active ? '✓' : ''}
      </span>
    </button>
  )
}
