import { useEffect, useRef, useState } from 'react'
import {
  logoutOtherSessions,
  set2faMethod,
  telegramLinkStart,
  telegramLinkStatus,
} from '../../api/generated/auth/auth'
import { useAuth } from '../../hooks/useAuth'
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
