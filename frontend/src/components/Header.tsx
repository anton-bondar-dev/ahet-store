import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useCartUI } from '../hooks/useCartUI'
import { useCart } from '../hooks/useCart'
import { useIsStaff } from '../hooks/useIsStaff'
import { useWishlist } from '../hooks/useWishlist'
import { SearchBar } from './SearchBar'

export function Header() {
  const { totalQuantity } = useCart()
  const { openDrawer } = useCartUI()
  const { user } = useAuth()
  const isStaff = useIsStaff()
  const { count: wishlistCount } = useWishlist()

  return (
    <header className="sticky top-0 z-[60] border-b border-gray-100 bg-white shadow-sm">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-3">
        {/* Logo / store name */}
        <Link
          to="/"
          className="shrink-0 text-xl font-bold text-gray-900 transition hover:text-gray-600"
        >
          Ahet Store
        </Link>

        {/* Search with autocomplete + history */}
        <SearchBar />

        {/* Cart — opens the mini-cart drawer (hidden for staff: they can't shop) */}
        {!isStaff && (
          <button
            type="button"
            onClick={openDrawer}
            className="inline-flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 hover:text-gray-900"
          >
            <svg
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="9" cy="21" r="1" />
              <circle cx="20" cy="21" r="1" />
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
            </svg>
            <span>Кошик ({totalQuantity})</span>
          </button>
        )}

        {/* Wishlist — customers only (staff don't shop) */}
        {user && !isStaff && (
          <Link
            to="/wishlist"
            className="inline-flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 hover:text-gray-900"
          >
            <svg
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
            </svg>
            <span>Обране{wishlistCount > 0 ? ` (${wishlistCount})` : ''}</span>
          </Link>
        )}

        {/* Staff: quick access to the Helpdesk from anywhere */}
        {isStaff && (
          <Link
            to="/support/admin"
            className="inline-flex shrink-0 items-center gap-2 rounded-md bg-gray-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-gray-700"
          >
            Панель підтримки
          </Link>
        )}

        {/* Auth state */}
        {user ? (
          <Link
            to="/account"
            className="inline-flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 hover:text-gray-900"
          >
            <svg
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <span className="max-w-[8rem] truncate">{user.first_name || user.username}</span>
          </Link>
        ) : (
          <Link
            to="/login"
            className="shrink-0 rounded-md px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 hover:text-gray-900"
          >
            Увійти
          </Link>
        )}
      </div>
    </header>
  )
}
