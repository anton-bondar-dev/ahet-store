import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  getGetMyChatQueryKey,
  useGetMyChat,
  useSendMyMessage,
} from '../api/generated/support/support'

// Floating support chat for logged-in customers. Every staff reply arrives
// pre-masked from the API as the single "ahetStore" help-desk identity — the
// widget never sees which admin actually answered.
export function SupportChatWidget() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  // Only poll while the panel is open; opening also (re)marks staff replies read.
  const chatQuery = useGetMyChat({
    query: { refetchInterval: open ? 4000 : false, enabled: open },
  })
  const sendMutation = useSendMyMessage({
    mutation: {
      onSuccess: () =>
        queryClient.invalidateQueries({ queryKey: getGetMyChatQueryKey() }),
    },
  })

  const messages = chatQuery.data?.data.messages ?? []

  // Keep the newest message in view whenever the thread grows or reopens.
  useEffect(() => {
    if (open && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages.length, open])

  const send = async () => {
    const trimmed = text.trim()
    if (!trimmed || sendMutation.isPending) return
    setText('')
    try {
      await sendMutation.mutateAsync({ data: { text: trimmed } })
    } catch {
      setText(trimmed) // restore so the user can retry
    }
  }

  return (
    <>
      {/* Launcher */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Чат підтримки"
        className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-gray-900 text-white shadow-lg transition hover:bg-gray-700"
      >
        {open ? (
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h8M8 8h8m-8 8h5m-9 4 1.5-3A8 8 0 1 1 20 12a8 8 0 0 1-14.5 4.5L4 20Z" />
          </svg>
        )}
      </button>

      {/* Panel */}
      {open && (
        <div className="fixed bottom-24 right-5 z-40 flex h-[28rem] w-[22rem] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl">
          <div className="flex items-center gap-2 border-b border-gray-100 bg-gray-900 px-4 py-3 text-white">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/15 text-sm font-bold">
              А
            </span>
            <div>
              <p className="text-sm font-semibold leading-tight">Підтримка ahetStore</p>
              <p className="text-xs text-white/60">Зазвичай відповідаємо швидко</p>
            </div>
          </div>

          <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto bg-gray-50 px-3 py-3">
            {chatQuery.isLoading ? (
              <p className="mt-6 text-center text-sm text-gray-400">Завантаження…</p>
            ) : messages.length === 0 ? (
              <p className="mt-6 text-center text-sm text-gray-400">
                Напишіть нам — ми на зв'язку!
              </p>
            ) : (
              messages.map((m) => {
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
              disabled={!text.trim() || sendMutation.isPending}
              aria-label="Надіслати"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gray-900 text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.5 4.5 21 12 3.5 19.5 6 12Zm0 0h6" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  )
}
