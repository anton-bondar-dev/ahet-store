import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  getGetTicketQueryKey,
  getListTicketsQueryKey,
  useCloseTicket,
  useGetTicket,
  useListTickets,
  useReplyTicket,
} from '../api/generated/support/support'
import { CustomerContext } from '../components/support/CustomerContext'
import { MetricsCard } from '../components/support/MetricsCard'
import { TaggedCommentsTab } from '../components/support/TaggedCommentsTab'
import { useAuth } from '../hooks/useAuth'

// Hardcoded quick replies to speed up common responses (fill the box, editable).
const QUICK_REPLIES = [
  'Вітаю! Уточніть, будь ласка, номер вашого замовлення.',
  'Дякуємо за звернення! Передав ваше питання спеціалісту.',
  'Питання вирішено. Гарного дня! 🙂',
]

type Tab = 'chats' | 'comments'

// Staff-only Helpdesk. Shows the REAL author of every message (the masking is
// only user-facing) plus workspace tools: metrics, tagged comments, customer
// context and a close-ticket action that triggers the customer's 👍/👎.
export function AdminSupportPage() {
  const navigate = useNavigate()
  const { user, isLoading } = useAuth()
  const [tab, setTab] = useState<Tab>('chats')

  useEffect(() => {
    if (isLoading) return
    if (!user) navigate('/login')
    else if (!user.is_staff) navigate('/')
  }, [isLoading, user, navigate])

  if (isLoading || !user?.is_staff) {
    return <p className="p-6 text-gray-500">Завантаження…</p>
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-4 flex items-center gap-2">
        <h1 className="text-2xl font-bold text-gray-900">Панель підтримки</h1>
        <span className="rounded-full bg-red-600 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-white">
          Адміністратор
        </span>
        <Link to="/account" className="ml-auto text-sm text-gray-500 hover:text-gray-900">
          ← Кабінет
        </Link>
      </div>

      <div className="mb-5">
        <MetricsCard />
      </div>

      {/* Tab switcher */}
      <div className="mb-4 flex gap-1 border-b border-gray-200">
        <TabButton active={tab === 'chats'} onClick={() => setTab('chats')}>
          Чати
        </TabButton>
        <TabButton active={tab === 'comments'} onClick={() => setTab('comments')}>
          Позначені коментарі
        </TabButton>
      </div>

      {tab === 'chats' ? <ChatsTab /> : <TaggedCommentsTab />}
    </div>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
        active
          ? 'border-gray-900 text-gray-900'
          : 'border-transparent text-gray-500 hover:text-gray-800'
      }`}
    >
      {children}
    </button>
  )
}

function ChatsTab() {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [text, setText] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  const ticketsQuery = useListTickets({ query: { refetchInterval: 5000 } })
  const ticketQuery = useGetTicket(selectedId ?? 0, {
    query: {
      enabled: selectedId != null,
      refetchInterval: selectedId != null ? 4000 : false,
    },
  })

  const invalidate = () => {
    if (selectedId != null) {
      queryClient.invalidateQueries({ queryKey: getGetTicketQueryKey(selectedId) })
    }
    queryClient.invalidateQueries({ queryKey: getListTicketsQueryKey() })
  }
  const replyMutation = useReplyTicket({ mutation: { onSuccess: invalidate } })
  const closeMutation = useCloseTicket({ mutation: { onSuccess: invalidate } })

  const tickets = ticketsQuery.data?.data ?? []
  const ticket = ticketQuery.data?.data
  const messages = ticket?.messages ?? []
  const isClosed = ticket?.status === 'closed'

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

  return (
    <div className="grid gap-4 lg:grid-cols-[16rem_1fr_15rem]">
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
                  <p className="text-xs text-gray-400">
                    {t.status === 'open' ? 'Відкрито' : 'Закрито'}
                  </p>
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
            <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-4 py-3">
              <p className="text-sm font-semibold text-gray-900">
                {ticket?.user_username ?? '…'}
                {isClosed && (
                  <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                    Закрито
                  </span>
                )}
              </p>
              {!isClosed && (
                <button
                  type="button"
                  onClick={() => closeMutation.mutateAsync({ ticketId: selectedId }).catch(() => {})}
                  disabled={closeMutation.isPending}
                  className="rounded-md border border-gray-300 px-3 py-1 text-xs font-medium text-gray-600 transition hover:bg-gray-50 disabled:opacity-60"
                >
                  Закрити звернення
                </button>
              )}
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
                      <p className={`mb-0.5 text-xs font-semibold ${staff ? 'text-white/70' : 'text-gray-500'}`}>
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

            {/* Quick replies */}
            <div className="flex flex-wrap gap-1.5 border-t border-gray-100 px-2 pt-2">
              {QUICK_REPLIES.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => setText(q)}
                  className="rounded-full border border-gray-200 px-2.5 py-1 text-xs text-gray-600 transition hover:bg-gray-100"
                >
                  {q.length > 28 ? `${q.slice(0, 28)}…` : q}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 p-2">
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

      {/* Customer context */}
      <div className="lg:block">
        {selectedId != null && <CustomerContext ticketId={selectedId} />}
      </div>
    </div>
  )
}
