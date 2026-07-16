import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  getGetTicketQueryKey,
  getListTicketsQueryKey,
  useGetTicket,
  useListTickets,
  useReplyTicket,
} from '../api/generated/support/support'
import { useAuth } from '../hooks/useAuth'

// Staff-only help-desk console. Unlike the customer widget, this side shows the
// REAL author of every message (sender_username / sender_name) so admins can see
// who on the team said what — the masking only applies to the user-facing API.
export function AdminSupportPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, isLoading } = useAuth()

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [text, setText] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isLoading) return
    if (!user) navigate('/login')
    else if (!user.is_staff) navigate('/')
  }, [isLoading, user, navigate])

  const ticketsQuery = useListTickets({
    query: { refetchInterval: 5000, enabled: !!user?.is_staff },
  })
  const ticketQuery = useGetTicket(selectedId ?? 0, {
    query: {
      enabled: selectedId != null && !!user?.is_staff,
      refetchInterval: selectedId != null ? 4000 : false,
    },
  })
  const replyMutation = useReplyTicket({
    mutation: {
      onSuccess: () => {
        if (selectedId != null) {
          queryClient.invalidateQueries({ queryKey: getGetTicketQueryKey(selectedId) })
        }
        queryClient.invalidateQueries({ queryKey: getListTicketsQueryKey() })
      },
    },
  })

  const tickets = ticketsQuery.data?.data ?? []
  const ticket = ticketQuery.data?.data
  const messages = ticket?.messages ?? []

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages.length, selectedId])

  const reply = async () => {
    const trimmed = text.trim()
    if (!trimmed || selectedId == null || replyMutation.isPending) return
    setText('')
    try {
      await replyMutation.mutateAsync({ ticketId: selectedId, data: { text: trimmed } })
    } catch {
      setText(trimmed)
    }
  }

  if (isLoading || !user?.is_staff) {
    return <p className="p-6 text-gray-500">Завантаження…</p>
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6 flex items-center gap-2">
        <h1 className="text-2xl font-bold text-gray-900">Панель підтримки</h1>
        <span className="rounded-full bg-red-600 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-white">
          Адміністратор
        </span>
        <Link to="/account" className="ml-auto text-sm text-gray-500 hover:text-gray-900">
          ← Кабінет
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-[18rem_1fr]">
        {/* Ticket list */}
        <aside className="rounded-lg border border-gray-200">
          <div className="border-b border-gray-100 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Звернення
          </div>
          <ul className="max-h-[32rem] divide-y divide-gray-100 overflow-y-auto">
            {tickets.length === 0 && (
              <li className="px-4 py-6 text-center text-sm text-gray-400">Поки що порожньо</li>
            )}
            {tickets.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(t.id)}
                  className={`flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition ${
                    selectedId === t.id ? 'bg-gray-100' : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">{t.user_username}</p>
                    <p className="text-xs text-gray-400">{t.status === 'open' ? 'Відкрито' : 'Закрито'}</p>
                  </div>
                  {(t.unread_count ?? 0) > 0 && (
                    <span className="shrink-0 rounded-full bg-red-600 px-2 py-0.5 text-xs font-semibold text-white">
                      {t.unread_count}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* Conversation */}
        <section className="flex h-[34rem] flex-col rounded-lg border border-gray-200">
          {selectedId == null ? (
            <div className="flex flex-1 items-center justify-center text-sm text-gray-400">
              Оберіть звернення зі списку
            </div>
          ) : (
            <>
              <div className="border-b border-gray-100 px-4 py-3">
                <p className="text-sm font-semibold text-gray-900">
                  {ticket?.user_username ?? '…'}
                </p>
              </div>
              <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto bg-gray-50 px-4 py-3">
                {messages.map((m) => {
                  const staff = m.from_staff
                  return (
                    <div key={m.id} className={`flex ${staff ? 'justify-end' : 'justify-start'}`}>
                      <div
                        className={`max-w-[75%] rounded-2xl px-3 py-2 text-sm ${
                          staff
                            ? 'rounded-br-sm bg-gray-900 text-white'
                            : 'rounded-bl-sm bg-white text-gray-900 ring-1 ring-gray-200'
                        }`}
                      >
                        <p
                          className={`mb-0.5 text-xs font-semibold ${
                            staff ? 'text-white/70' : 'text-gray-500'
                          }`}
                        >
                          {m.sender_name} · @{m.sender_username}
                        </p>
                        <p className="whitespace-pre-wrap break-words">{m.text}</p>
                      </div>
                    </div>
                  )
                })}
                {messages.length === 0 && (
                  <p className="mt-6 text-center text-sm text-gray-400">Повідомлень немає</p>
                )}
              </div>
              <div className="flex items-center gap-2 border-t border-gray-100 p-2">
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      reply()
                    }
                  }}
                  placeholder="Відповідь від імені ahetStore…"
                  className="min-w-0 flex-1 rounded-full border border-gray-300 px-4 py-2 text-sm text-gray-900 focus:border-gray-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={reply}
                  disabled={!text.trim() || replyMutation.isPending}
                  className="shrink-0 rounded-full bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Надіслати
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
