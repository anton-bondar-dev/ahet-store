import { useEffect } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { roleLabel } from '../lib/roles'
import { BonusCard } from './account/BonusCard'
import { CommentsTab } from './account/CommentsTab'
import { OrdersTab } from './account/OrdersTab'
import { PersonalInfoTab } from './account/PersonalInfoTab'
import { SecurityTab } from './account/SecurityTab'
import { ViewedTab } from './account/ViewedTab'

const TABS = [
  { key: 'profile', label: 'Особистий кабінет' },
  { key: 'orders', label: 'Мої замовлення' },
  { key: 'viewed', label: 'Історія переглядів' },
  { key: 'comments', label: 'Мої коментарі' },
  { key: 'security', label: 'Безпека & 2FA' },
]

// Support staff use a stripped-down account: only their profile name — no
// buyer tabs (orders, history, reviews), no bonuses, no Security/2FA.
const STAFF_TAB_KEYS = new Set(['profile'])

export function AccountPage() {
  const navigate = useNavigate()
  const { user, isLoading, logout } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()

  useEffect(() => {
    if (!isLoading && !user) navigate('/login')
  }, [isLoading, user, navigate])

  if (isLoading) return <p className="p-6 text-gray-500">Завантаження…</p>
  if (!user) return null

  const tabs = user.is_staff ? TABS.filter((t) => STAFF_TAB_KEYS.has(t.key)) : TABS
  const requested = searchParams.get('tab') ?? 'profile'
  // Fall back to the first visible tab if the URL asks for a hidden one.
  const active = tabs.some((t) => t.key === requested) ? requested : tabs[0].key

  const selectTab = (key: string) =>
    setSearchParams((prev) => {
      prev.set('tab', key)
      return prev
    })

  return (
    <div className="mx-auto max-w-5xl p-6">
      {/* Header: greeting + bonus card */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-gray-900">Мій акаунт</h1>
            {roleLabel(user) && (
              <span className="rounded-full bg-red-600 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-white">
                {roleLabel(user)}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500">{user.email || user.username}</p>
        </div>
        <div className="sm:w-64">
          {user.is_staff ? (
            <Link
              to="/support/admin"
              className="flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-gray-700"
            >
              Відкрити панель підтримки →
            </Link>
          ) : (
            <BonusCard balance={user.bonus_balance ?? 0} />
          )}
        </div>
      </div>

      <div className="flex flex-col gap-6 md:flex-row">
        {/* Sidebar nav */}
        <aside className="md:w-56 md:shrink-0">
          <nav className="flex gap-2 overflow-x-auto md:flex-col md:overflow-visible">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => selectTab(tab.key)}
                className={`whitespace-nowrap rounded-md px-3 py-2 text-left text-sm transition ${
                  active === tab.key
                    ? 'bg-gray-100 font-semibold text-gray-900'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
            {/* Customers reach their wishlist and their own chat here. */}
            {!user.is_staff && (
              <Link
                to="/wishlist"
                className="whitespace-nowrap rounded-md px-3 py-2 text-left text-sm text-gray-600 transition hover:bg-gray-50 hover:text-gray-900 md:mt-2 md:border-t md:border-gray-100 md:pt-3"
              >
                Моє обране
              </Link>
            )}
            {!user.is_staff && (
              <Link
                to="/me/support"
                className="whitespace-nowrap rounded-md px-3 py-2 text-left text-sm text-gray-600 transition hover:bg-gray-50 hover:text-gray-900 md:mt-2 md:border-t md:border-gray-100 md:pt-3"
              >
                Підтримка
              </Link>
            )}
            {user.is_staff && (
              <Link
                to="/support/admin"
                className="whitespace-nowrap rounded-md px-3 py-2 text-left text-sm font-medium text-red-700 transition hover:bg-red-50"
              >
                Панель підтримки
              </Link>
            )}
            <button
              type="button"
              onClick={() => {
                logout()
                navigate('/')
              }}
              className="whitespace-nowrap rounded-md px-3 py-2 text-left text-sm text-gray-600 transition hover:bg-gray-50 hover:text-red-600 md:mt-2 md:border-t md:border-gray-100 md:pt-3"
            >
              Вийти
            </button>
          </nav>
        </aside>

        {/* Content */}
        <main className="min-w-0 flex-1">
          {active === 'profile' && <PersonalInfoTab nameOnly={user.is_staff} />}
          {active === 'orders' && <OrdersTab />}
          {active === 'viewed' && <ViewedTab />}
          {active === 'comments' && <CommentsTab />}
          {active === 'security' && <SecurityTab />}
        </main>
      </div>
    </div>
  )
}
