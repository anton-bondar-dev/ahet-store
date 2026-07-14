import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
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

export function AccountPage() {
  const navigate = useNavigate()
  const { user, isLoading, logout } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const active = searchParams.get('tab') ?? 'profile'

  useEffect(() => {
    if (!isLoading && !user) navigate('/login')
  }, [isLoading, user, navigate])

  if (isLoading) return <p className="p-6 text-gray-500">Завантаження…</p>
  if (!user) return null

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
          <h1 className="text-2xl font-bold text-gray-900">Мій акаунт</h1>
          <p className="text-sm text-gray-500">{user.email || user.username}</p>
        </div>
        <div className="sm:w-64">
          <BonusCard balance={user.bonus_balance ?? 0} />
        </div>
      </div>

      <div className="flex flex-col gap-6 md:flex-row">
        {/* Sidebar nav */}
        <aside className="md:w-56 md:shrink-0">
          <nav className="flex gap-2 overflow-x-auto md:flex-col md:overflow-visible">
            {TABS.map((tab) => (
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
          {active === 'profile' && <PersonalInfoTab />}
          {active === 'orders' && <OrdersTab />}
          {active === 'viewed' && <ViewedTab />}
          {active === 'comments' && <CommentsTab />}
          {active === 'security' && <SecurityTab />}
        </main>
      </div>
    </div>
  )
}
