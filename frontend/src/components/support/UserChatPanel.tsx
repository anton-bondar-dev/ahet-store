import { useEffect, useRef, useState } from 'react'
import type { UserChatMessageOut } from '../../api/generated/onlineStoreAPI.schemas'

// Presentational chat body (message list + composer) shared by the floating
// widget and the full-page dashboard view. Every staff message already arrives
// masked as "ahetStore" from the API — this component never sees who replied.
export function UserChatPanel({
  messages,
  isLoading,
  sending,
  onSend,
  canRate = false,
  onRate,
  status = 'none',
  onEnd,
  ending = false,
}: {
  messages: UserChatMessageOut[]
  isLoading: boolean
  sending: boolean
  onSend: (text: string) => Promise<unknown>
  canRate?: boolean
  onRate?: (isPositive: boolean) => Promise<unknown>
  status?: string
  onEnd?: () => Promise<unknown>
  ending?: boolean
}) {
  const [text, setText] = useState('')
  const [confirmEnd, setConfirmEnd] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  const handleEnd = async () => {
    try {
      await onEnd?.()
    } finally {
      setConfirmEnd(false)
    }
  }

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages.length])

  const send = async () => {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    setText('')
    try {
      await onSend(trimmed)
    } catch {
      setText(trimmed) // restore on failure so the user can retry
    }
  }

  return (
    <>
      {/* End-chat control — only while there's an active (open) conversation. */}
      {status === 'open' && onEnd && (
        <div className="flex items-center justify-end border-b border-gray-100 bg-white px-3 py-1.5">
          {confirmEnd ? (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-gray-500">Завершити чат?</span>
              <button
                type="button"
                onClick={handleEnd}
                disabled={ending}
                className="font-semibold text-red-600 transition hover:underline disabled:opacity-50"
              >
                Так
              </button>
              <button
                type="button"
                onClick={() => setConfirmEnd(false)}
                disabled={ending}
                className="text-gray-500 transition hover:underline"
              >
                Скасувати
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmEnd(true)}
              className="text-xs font-medium text-gray-500 transition hover:text-gray-800"
            >
              Завершити чат
            </button>
          )}
        </div>
      )}

      <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto bg-gray-50 px-3 py-3">
        {isLoading ? (
          <p className="mt-6 text-center text-sm text-gray-400">Завантаження…</p>
        ) : messages.length === 0 ? (
          <p className="mt-6 text-center text-sm text-gray-400">
            Напишіть нам — ми на зв'язку!
          </p>
        ) : (
          messages.map((m) => {
            if (m.sender === 'system') {
              return (
                <div key={m.id} className="flex justify-center">
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-center text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
                    {m.text}
                  </span>
                </div>
              )
            }
            const mine = m.sender === 'user'
            return (
              <div key={m.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                    mine
                      ? 'rounded-br-sm bg-gray-900 text-white'
                      : 'rounded-bl-sm bg-white text-gray-900 ring-1 ring-gray-200'
                  }`}
                >
                  {!mine && (
                    <p className="mb-0.5 text-xs font-semibold text-emerald-700">
                      {m.author_name}
                    </p>
                  )}
                  <p className="whitespace-pre-wrap break-words">{m.text}</p>
                </div>
              </div>
            )
          })
        )}
      </div>

      {canRate && onRate && (
        <div className="flex items-center justify-between gap-2 border-t border-gray-100 bg-emerald-50 px-3 py-2">
          <span className="text-sm text-emerald-800">Оцініть підтримку:</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onRate(true).catch(() => {})}
              aria-label="Добре"
              className="rounded-full px-2 py-1 text-lg transition hover:bg-emerald-100"
            >
              👍
            </button>
            <button
              type="button"
              onClick={() => onRate(false).catch(() => {})}
              aria-label="Погано"
              className="rounded-full px-2 py-1 text-lg transition hover:bg-emerald-100"
            >
              👎
            </button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 border-t border-gray-100 p-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              send()
            }
          }}
          placeholder="Ваше повідомлення…"
          className="min-w-0 flex-1 rounded-full border border-gray-300 px-4 py-2 text-sm text-gray-900 focus:border-gray-500 focus:outline-none"
        />
        <button
          type="button"
          onClick={send}
          disabled={!text.trim() || sending}
          aria-label="Надіслати"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gray-900 text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.5 4.5 21 12 3.5 19.5 6 12Zm0 0h6" />
          </svg>
        </button>
      </div>
    </>
  )
}
