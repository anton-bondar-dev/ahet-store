import { useEffect } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { UserChatPanel } from '../components/support/UserChatPanel'
import { useAuth } from '../hooks/useAuth'
import { useIsStaff } from '../hooks/useIsStaff'
import { useSupportChat } from '../hooks/useSupportChat'

// Dedicated full-page support conversation for the user dashboard (/me/support).
// Shares the same chat cache as the floating widget (which hides itself on this
// route, so there is never a duplicate chat UI).
export function UserSupportPage() {
  const navigate = useNavigate()
  const { user, isLoading: authLoading } = useAuth()
  const isStaff = useIsStaff()
  const { messages, isLoading, sending, send, canRate, rate } = useSupportChat(4000)

  useEffect(() => {
    if (!authLoading && !user) navigate('/login')
  }, [authLoading, user, navigate])

  if (authLoading) return <p className="p-6 text-gray-500">Завантаження…</p>
  if (!user) return null
  // Staff use the Helpdesk console, not the customer support view.
  if (isStaff) return <Navigate to="/support/admin" replace />

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center gap-2">
        <h1 className="text-2xl font-bold text-gray-900">Підтримка</h1>
        <Link to="/account" className="ml-auto text-sm text-gray-500 hover:text-gray-900">
          ← Кабінет
        </Link>
      </div>

      <div className="flex h-[36rem] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-gray-100 bg-gray-900 px-4 py-3 text-white">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/15 text-sm font-bold">
            А
          </span>
          <div>
            <p className="text-sm font-semibold leading-tight">Підтримка ahetStore</p>
            <p className="text-xs text-white/60">Ми на зв'язку — напишіть нам</p>
          </div>
        </div>
        <UserChatPanel
          messages={messages}
          isLoading={isLoading}
          sending={sending}
          onSend={send}
          canRate={canRate}
          onRate={rate}
        />
      </div>
    </div>
  )
}
