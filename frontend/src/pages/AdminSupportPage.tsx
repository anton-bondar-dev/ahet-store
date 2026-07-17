import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  getGetTicketQueryKey,
  getListTicketsQueryKey,
  renderMacroForTicket,
  useAssignTicket,
  useCancelBonus,
  useCloseTicket,
  useGetTicket,
  useImpersonateUser,
  useListApprovals,
  useListMacros,
  useListStaff,
  useListTickets,
  useReplyTicket,
  useSetOperatorStatus,
  useSetPriority,
  useTicketAction,
  useTicketPresence,
} from '../api/generated/support/support'
import { ApprovalsTab } from '../components/support/ApprovalsTab'
import { AuditLogTab } from '../components/support/AuditLogTab'
import { CustomerContext } from '../components/support/CustomerContext'
import { MacrosTab } from '../components/support/MacrosTab'
import { MetricsCard } from '../components/support/MetricsCard'
import { StaffTable } from '../components/support/StaffTable'
import { TaggedCommentsTab } from '../components/support/TaggedCommentsTab'
import { useAuth } from '../hooks/useAuth'
import { startImpersonation } from '../lib/impersonation'
import { roleLabel } from '../lib/roles'

const PRIORITY_META: Record<string, { label: string; cls: string; dot: string }> = {
  low: { label: 'Низький', cls: 'border-gray-300 bg-gray-100 text-gray-600', dot: 'bg-gray-400' },
  normal: { label: 'Звичайний', cls: 'border-gray-300 bg-white text-gray-600', dot: 'bg-gray-300' },
  high: { label: 'Високий', cls: 'border-orange-300 bg-orange-100 text-orange-700', dot: 'bg-orange-500' },
  urgent: { label: 'Терміновий', cls: 'border-red-300 bg-red-100 text-red-700', dot: 'bg-red-500' },
}

const QUICK_REPLIES = [
  'Вітаю! Уточніть, будь ласка, номер вашого замовлення.',
  'Дякуємо за звернення! Передав ваше питання спеціалісту.',
  'Питання вирішено. Гарного дня! 🙂',
]

type Tab = 'chats' | 'comments' | 'macros' | 'audit' | 'staff' | 'approvals'

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

  const isOwner = !!user.is_superuser

  return <Workspace isOwner={isOwner} user={user} tab={tab} setTab={setTab} />
}

function Workspace({
  isOwner,
  user,
  tab,
  setTab,
}: {
  isOwner: boolean
  user: { is_superuser?: boolean; is_staff?: boolean }
  tab: Tab
  setTab: (t: Tab) => void
}) {
  // Owner-only: count of pending approvals for the tab badge.
  const approvalsQuery = useListApprovals({
    query: { enabled: isOwner, refetchInterval: isOwner ? 8000 : false },
  })
  const pendingCount = approvalsQuery.data?.data.length ?? 0

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-4 flex items-center gap-2">
        <h1 className="text-2xl font-bold text-gray-900">Панель підтримки</h1>
        <span className="rounded-full bg-red-600 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-white">
          {roleLabel(user)}
        </span>
        <StatusToggle />
        <Link to="/account" className="text-sm text-gray-500 hover:text-gray-900">
          ← Кабінет
        </Link>
      </div>

      <div className="mb-5">
        <MetricsCard />
      </div>

      <div className="mb-4 flex gap-1 border-b border-gray-200">
        <TabButton active={tab === 'chats'} onClick={() => setTab('chats')}>Чати</TabButton>
        <TabButton active={tab === 'comments'} onClick={() => setTab('comments')}>Позначені коментарі</TabButton>
        <TabButton active={tab === 'macros'} onClick={() => setTab('macros')}>Макроси</TabButton>
        {isOwner && (
          <TabButton active={tab === 'approvals'} onClick={() => setTab('approvals')}>
            Запити{pendingCount > 0 ? ` (${pendingCount})` : ''} 🔒
          </TabButton>
        )}
        {isOwner && (
          <TabButton active={tab === 'staff'} onClick={() => setTab('staff')}>Оператори 🔒</TabButton>
        )}
        {isOwner && (
          <TabButton active={tab === 'audit'} onClick={() => setTab('audit')}>Журнал 🔒</TabButton>
        )}
      </div>

      {tab === 'chats' && <ChatsTab isOwner={isOwner} />}
      {tab === 'comments' && <TaggedCommentsTab />}
      {tab === 'macros' && <MacrosTab />}
      {tab === 'approvals' && isOwner && <ApprovalsTab />}
      {tab === 'staff' && isOwner && <StaffTable />}
      {tab === 'audit' && isOwner && <AuditLogTab />}
    </div>
  )
}

function AssignControl({
  ticketId,
  assignedName,
  isOwner,
  onDone,
}: {
  ticketId: number
  assignedName: string | null
  isOwner: boolean
  onDone: () => void
}) {
  const assign = useAssignTicket({ mutation: { onSuccess: onDone } })
  const staffQuery = useListStaff({ query: { enabled: isOwner } })
  const operators = (staffQuery.data?.data ?? []).filter((s) => s.role === 'operator' && s.is_active)

  return (
    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
      <span className="text-gray-500">
        {assignedName ? (
          <>
            Призначено: <strong className="text-gray-800">{assignedName}</strong>
          </>
        ) : (
          'Не призначено'
        )}
      </span>
      <button
        type="button"
        onClick={() => assign.mutate({ ticketId, data: {} })}
        className="rounded border border-gray-300 px-2 py-0.5 text-gray-600 hover:bg-gray-50"
      >
        Взяти собі
      </button>
      {isOwner && operators.length > 0 && (
        <select
          value=""
          onChange={(e) => {
            const id = Number(e.target.value)
            if (id) assign.mutate({ ticketId, data: { operator_id: id } })
            e.currentTarget.value = ''
          }}
          className="rounded border border-gray-300 px-1 py-0.5 text-gray-600"
        >
          <option value="">Призначити…</option>
          {operators.map((o) => (
            <option key={o.id} value={o.id}>{o.name}</option>
          ))}
        </select>
      )}
    </div>
  )
}

function StatusToggle() {
  const { user, refreshUser } = useAuth()
  const setStatus = useSetOperatorStatus()
  const away = user?.operator_status === 'away'
  const toggle = async () => {
    await setStatus.mutateAsync({ data: { status: away ? 'online' : 'away' } }).catch(() => {})
    refreshUser()
  }
  return (
    <button
      type="button"
      onClick={toggle}
      className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-gray-200 px-3 py-1 text-xs font-medium text-gray-700 transition hover:bg-gray-50"
      title="Перемкнути доступність"
    >
      <span className={`h-2 w-2 rounded-full ${away ? 'bg-gray-300' : 'bg-emerald-500'}`} />
      {away ? 'Відійшов' : 'Онлайн'}
    </button>
  )
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
        active ? 'border-gray-900 text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-800'
      }`}
    >
      {children}
    </button>
  )
}

function ChatsTab({ isOwner }: { isOwner: boolean }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { refreshUser } = useAuth()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [search, setSearch] = useState('')
  const [text, setText] = useState('')
  const [internalMode, setInternalMode] = useState(false)
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const lastTypingRef = useRef(0)

  const ticketsQuery = useListTickets(
    { archived: showArchived },
    { query: { refetchInterval: 5000 } },
  )
  const ticketQuery = useGetTicket(selectedId ?? 0, {
    query: { enabled: selectedId != null, refetchInterval: selectedId != null ? 4000 : false },
  })
  const macrosQuery = useListMacros({ query: { enabled: selectedId != null } })

  const invalidate = () => {
    if (selectedId != null) queryClient.invalidateQueries({ queryKey: getGetTicketQueryKey(selectedId) })
    queryClient.invalidateQueries({ queryKey: getListTicketsQueryKey() })
  }
  const replyMutation = useReplyTicket({ mutation: { onSuccess: invalidate } })
  const closeMutation = useCloseTicket({ mutation: { onSuccess: invalidate } })
  const actionMutation = useTicketAction({
    mutation: {
      onSuccess: (res) => {
        invalidate()
        const pending = res.data.pending
        setActionMsg(pending ? 'Надіслано тімліду на підтвердження ⏳' : 'Виконано ✓')
        setTimeout(() => setActionMsg(null), 4000)
      },
    },
  })
  const cancelBonusMutation = useCancelBonus({ mutation: { onSuccess: invalidate } })
  const priorityMutation = useSetPriority({ mutation: { onSuccess: invalidate } })
  const presenceMutation = useTicketPresence()
  const impersonateMutation = useImpersonateUser()

  const allTickets = ticketsQuery.data?.data ?? []
  const q = search.trim().toLowerCase()
  const tickets = q
    ? allTickets.filter(
        (t) =>
          t.user_username.toLowerCase().includes(q) ||
          (t.support_id ?? '').toLowerCase().includes(q) ||
          (t.assigned_to ?? '').toLowerCase().includes(q),
      )
    : allTickets
  const ticket = ticketQuery.data?.data
  const messages = ticket?.messages ?? []
  const isClosed = ticket?.status === 'closed'
  const viewers = ticket?.viewers ?? []
  const macros = macrosQuery.data?.data ?? []

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages.length, selectedId])

  // Opening a ticket marks its messages read on the server; refresh the queue so
  // the unread badge clears right away instead of after the next poll.
  useEffect(() => {
    if (selectedId == null) return
    const t = setTimeout(
      () => queryClient.invalidateQueries({ queryKey: getListTicketsQueryKey() }),
      600,
    )
    return () => clearTimeout(t)
  }, [selectedId, queryClient])

  const onType = (value: string) => {
    setText(value)
    // Throttle "typing" heartbeats so collision detection isn't spammed.
    const now = Date.now()
    if (selectedId != null && value && now - lastTypingRef.current > 2500) {
      lastTypingRef.current = now
      presenceMutation.mutate({ ticketId: selectedId, data: { state: 'typing' } })
    }
  }

  const reply = async () => {
    const trimmed = text.trim()
    if (!trimmed || selectedId == null || replyMutation.isPending) return
    setText('')
    try {
      await replyMutation.mutateAsync({
        ticketId: selectedId,
        data: { text: trimmed, is_internal: internalMode },
      })
    } catch {
      setText(trimmed)
    }
  }

  const insertMacro = async (macroId: number) => {
    if (selectedId == null) return
    try {
      const res = await renderMacroForTicket(macroId, { ticket_id: selectedId })
      setText(res.data.content)
    } catch {
      /* ignore */
    }
  }

  const impersonate = async () => {
    if (!ticket) return
    try {
      const res = await impersonateMutation.mutateAsync({ userId: ticket.user_id })
      startImpersonation(res.data.access, res.data.target_name)
      await refreshUser()
      navigate('/')
    } catch {
      /* ignore */
    }
  }

  const typingViewer = viewers.find((v) => v.state === 'typing')
  const anyViewer = viewers[0]

  return (
    <div className="grid gap-4 lg:grid-cols-[16rem_1fr_16rem]">
      {/* Ticket list */}
      <aside className="rounded-lg border border-gray-200">
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            {showArchived ? 'Архів' : 'Звернення'}
          </span>
          <button
            type="button"
            onClick={() => { setShowArchived((v) => !v); setSelectedId(null) }}
            className="text-xs font-medium text-gray-500 hover:text-gray-900"
          >
            {showArchived ? '← Активні' : 'Архів'}
          </button>
        </div>
        <div className="border-b border-gray-100 p-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Пошук: клієнт, ID, оператор…"
            className="w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs focus:border-gray-400 focus:outline-none"
          />
        </div>
        <ul className="max-h-[32rem] divide-y divide-gray-100 overflow-y-auto">
          {tickets.length === 0 && <li className="px-4 py-6 text-center text-sm text-gray-400">Поки що порожньо</li>}
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
                  <p className="flex items-center gap-1.5 truncate text-sm font-medium text-gray-900">
                    {t.priority && t.priority !== 'normal' && (
                      <span
                        className={`h-2 w-2 shrink-0 rounded-full ${PRIORITY_META[t.priority]?.dot ?? 'bg-gray-300'}`}
                        title={`Пріоритет: ${PRIORITY_META[t.priority]?.label ?? t.priority}`}
                      />
                    )}
                    {t.is_overdue && <span title="Прострочено (SLA)">🚨</span>}
                    <span className="truncate">{t.user_username}</span>
                  </p>
                  <p className="truncate text-xs text-gray-400">
                    {t.support_id && <span className="font-mono">{t.support_id}</span>}
                    {t.assigned_to && <span> · 👤 {t.assigned_to}</span>}
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
      <section className="flex h-[34rem] min-w-0 flex-col rounded-lg border border-gray-200">
        {selectedId == null ? (
          <div className="flex flex-1 items-center justify-center text-sm text-gray-400">
            Оберіть звернення зі списку
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-gray-900">
                  {ticket?.customer_name ?? '…'}
                  {ticket?.is_overdue && <span className="ml-1" title="Прострочено">🚨</span>}
                  {isClosed && (
                    <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">Закрито</span>
                  )}
                </p>
                {ticket?.customer_support_id && (
                  <p className="font-mono text-xs text-gray-400">{ticket.customer_support_id}</p>
                )}
                {anyViewer && (
                  <p className="text-xs text-amber-600">
                    {typingViewer
                      ? `${typingViewer.staff_name} друкує…`
                      : `${anyViewer.staff_name} переглядає цей чат`}
                  </p>
                )}
                <AssignControl
                  ticketId={selectedId}
                  assignedName={ticket?.assigned_to_name ?? null}
                  isOwner={isOwner}
                  onDone={invalidate}
                />
              </div>
              <div className="flex shrink-0 items-start gap-2">
                <select
                  value={ticket?.priority ?? 'normal'}
                  onChange={(e) => priorityMutation.mutate({ ticketId: selectedId, data: { priority: e.target.value } })}
                  className={`rounded-md border px-2 py-1 text-xs font-semibold focus:outline-none ${PRIORITY_META[ticket?.priority ?? 'normal'].cls}`}
                  title="Пріоритет"
                >
                  {Object.entries(PRIORITY_META).map(([key, m]) => (
                    <option key={key} value={key}>{m.label}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={impersonate}
                  disabled={impersonateMutation.isPending}
                  className="rounded-md border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-600 transition hover:bg-gray-50 disabled:opacity-60"
                  title="Переглянути магазин очима клієнта"
                >
                  Увійти як клієнт
                </button>
                {!isClosed && (
                  <button
                    type="button"
                    onClick={() => closeMutation.mutateAsync({ ticketId: selectedId }).catch(() => {})}
                    disabled={closeMutation.isPending}
                    className="rounded-md border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-600 transition hover:bg-gray-50 disabled:opacity-60"
                  >
                    Закрити
                  </button>
                )}
              </div>
            </div>

            <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto bg-gray-50 px-4 py-3">
              {messages.map((m) => {
                if (m.is_system) {
                  const canCancel =
                    m.meta?.action === 'grant_bonuses' && !m.meta?.reversed
                  return (
                    <div key={m.id} className="flex flex-col items-center gap-0.5">
                      <span className="rounded-full bg-emerald-50 px-3 py-1 text-center text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
                        {m.text}
                      </span>
                      {canCancel && (
                        <button
                          type="button"
                          onClick={() => cancelBonusMutation.mutate({ ticketId: selectedId, data: { message_id: m.id } })}
                          className="text-[11px] text-red-500 underline hover:text-red-700"
                        >
                          Скасувати нарахування
                        </button>
                      )}
                    </div>
                  )
                }
                if (m.is_internal) {
                  return (
                    <div key={m.id} className="flex justify-end">
                      <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-amber-100 px-3 py-2 text-sm text-amber-900 ring-1 ring-amber-300">
                        <p className="mb-0.5 text-xs font-semibold text-amber-700">
                          🔒 Внутрішня нотатка · {m.sender_name}
                        </p>
                        <p className="whitespace-pre-wrap break-words">{m.text}</p>
                      </div>
                    </div>
                  )
                }
                const staff = m.from_staff
                return (
                  <div key={m.id} className={`flex ${staff ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[75%] rounded-2xl px-3 py-2 text-sm ${staff ? 'rounded-br-sm bg-gray-900 text-white' : 'rounded-bl-sm bg-white text-gray-900 ring-1 ring-gray-200'}`}>
                      <p className={`mb-0.5 text-xs font-semibold ${staff ? 'text-white/70' : 'text-gray-500'}`}>
                        {m.sender_name} · @{m.sender_username}
                      </p>
                      <p className="whitespace-pre-wrap break-words">{m.text}</p>
                    </div>
                  </div>
                )
              })}
              {messages.length === 0 && <p className="mt-6 text-center text-sm text-gray-400">Повідомлень немає</p>}
            </div>

            {/* Actionable chat (bonuses / coupons) */}
            <ActionBar
              onGrant={(amount) => actionMutation.mutate({ ticketId: selectedId, data: { type: 'grant_bonuses', amount } })}
              onCoupon={(percent) => actionMutation.mutate({ ticketId: selectedId, data: { type: 'generate_coupon', percent } })}
              note={actionMsg}
            />

            {/* Unified quick-replies + macros: one horizontally-scrollable row */}
            <div className="flex min-w-0 gap-1.5 overflow-x-auto whitespace-nowrap px-2 py-1 scrollbar-hide">
              {QUICK_REPLIES.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => setText(q)}
                  title={q}
                  className="shrink-0 rounded-full border border-gray-200 px-2.5 py-1 text-xs text-gray-600 transition hover:bg-gray-100"
                >
                  {q.length > 30 ? `${q.slice(0, 30)}…` : q}
                </button>
              ))}
              {macros.map((m) => (
                <button
                  key={`macro-${m.id}`}
                  type="button"
                  onClick={() => insertMacro(m.id)}
                  title={`Макрос: ${m.title}`}
                  className="shrink-0 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 transition hover:bg-indigo-100"
                >
                  ⚡ {m.title}
                </button>
              ))}
            </div>

            <label className="flex items-center gap-1.5 px-3 pt-1 text-xs text-gray-600">
              <input
                type="checkbox"
                checked={internalMode}
                onChange={(e) => setInternalMode(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-gray-300 text-amber-600 focus:ring-amber-500"
              />
              Внутрішня нотатка (не видно клієнту)
            </label>
            <div className="flex items-center gap-2 p-2">
              <input
                value={text}
                onChange={(e) => onType(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    reply()
                  }
                }}
                placeholder={internalMode ? 'Внутрішня нотатка для команди…' : 'Відповідь від імені ahetStore…'}
                className={`min-w-0 flex-1 rounded-full border px-4 py-2 text-sm focus:outline-none ${
                  internalMode
                    ? 'border-amber-300 bg-amber-50 text-amber-900 focus:border-amber-400'
                    : 'border-gray-300 text-gray-900 focus:border-gray-500'
                }`}
              />
              <button
                type="button"
                onClick={reply}
                disabled={!text.trim() || replyMutation.isPending}
                className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-50 ${
                  internalMode ? 'bg-amber-600 hover:bg-amber-700' : 'bg-gray-900 hover:bg-gray-700'
                }`}
              >
                {internalMode ? 'Додати нотатку' : 'Надіслати'}
              </button>
            </div>
          </>
        )}
      </section>

      {/* Customer context */}
      <div>
        {selectedId != null && ticket && (
          <CustomerContext
            ticketId={selectedId}
            userId={ticket.user_id}
            tags={ticket.tags}
            supportId={ticket.customer_support_id}
            lastSeen={ticket.customer_last_seen}
            device={ticket.customer_device}
            online={ticket.customer_online}
            isOwner={isOwner}
            blocked={ticket.customer_blocked}
          />
        )}
      </div>
    </div>
  )
}

const MAX_BONUS = 5000
const MAX_PERCENT = 100

function ActionBar({
  onGrant,
  onCoupon,
  note,
}: {
  onGrant: (amount: number) => void
  onCoupon: (percent: number) => void
  note: string | null
}) {
  const [open, setOpen] = useState<'bonus' | 'coupon' | null>(null)
  const [value, setValue] = useState('')

  const submit = () => {
    const cap = open === 'bonus' ? MAX_BONUS : MAX_PERCENT
    const n = Math.min(parseInt(value, 10) || 0, cap)
    if (n <= 0) return
    if (open === 'bonus') onGrant(n)
    if (open === 'coupon') onCoupon(n)
    setValue('')
    setOpen(null)
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 border-t border-gray-100 px-2 pt-2">
      {note && <span className="w-full text-xs text-amber-600">{note}</span>}
      <button type="button" onClick={() => setOpen(open === 'bonus' ? null : 'bonus')} className="rounded-md bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800 hover:bg-amber-200">
        🎁 Бонуси
      </button>
      <button type="button" onClick={() => setOpen(open === 'coupon' ? null : 'coupon')} className="rounded-md bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-800 hover:bg-emerald-200">
        🎟 Купон
      </button>
      {open && (
        <div className="flex items-center gap-1">
          <input
            autoFocus
            type="number"
            min={1}
            max={open === 'bonus' ? MAX_BONUS : MAX_PERCENT}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder={open === 'bonus' ? `к-сть (макс ${MAX_BONUS})` : `% (макс ${MAX_PERCENT})`}
            className="w-28 rounded-md border border-gray-300 px-2 py-1 text-xs focus:outline-none"
          />
          <button type="button" onClick={submit} className="rounded-md bg-gray-900 px-2 py-1 text-xs font-semibold text-white hover:bg-gray-700">
            OK
          </button>
        </div>
      )}
    </div>
  )
}
