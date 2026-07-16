import { useNavigate } from 'react-router-dom'
import { useEndImpersonation } from '../api/generated/support/support'
import { useAuth } from '../hooks/useAuth'
import { useImpersonation } from '../hooks/useImpersonation'
import { stopImpersonation } from '../lib/impersonation'

// Persistent banner shown while a staff member is viewing the storefront as a
// customer, with a one-click exit back to the Helpdesk.
export function ImpersonationBanner() {
  const { name, active } = useImpersonation()
  const { refreshUser } = useAuth()
  const navigate = useNavigate()
  const endMutation = useEndImpersonation()

  if (!active) return null

  const exit = async () => {
    stopImpersonation() // interceptor falls back to the staff token from here on
    endMutation.mutate() // logs impersonate_end (as staff)
    await refreshUser()
    navigate('/support/admin')
  }

  return (
    <div className="sticky top-0 z-[70] flex items-center justify-center gap-3 bg-amber-500 px-4 py-2 text-sm font-medium text-white">
      <span>
        Режим перегляду від імені клієнта: <strong>{name}</strong> — оформлення замовлень вимкнено
      </span>
      <button
        type="button"
        onClick={exit}
        className="rounded-md bg-white/20 px-3 py-1 text-xs font-semibold transition hover:bg-white/30"
      >
        Вийти з режиму
      </button>
    </div>
  )
}
