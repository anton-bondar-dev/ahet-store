import { Route, Routes, useLocation } from 'react-router-dom'
import App from '../App'
import { useAuth } from '../hooks/useAuth'
import { useCartUI } from '../hooks/useCartUI'
import { AccountPage } from '../pages/AccountPage'
import { AdminSupportPage } from '../pages/AdminSupportPage'
import { CartPage } from '../pages/CartPage'
import { CheckoutPage } from '../pages/CheckoutPage'
import { LoginPage } from '../pages/LoginPage'
import { OrderSuccessPage } from '../pages/OrderSuccessPage'
import { ProductDetail } from '../pages/ProductDetail'
import { RegisterPage } from '../pages/RegisterPage'
import { UserSupportPage } from '../pages/UserSupportPage'
import { Header } from './Header'
import { SupportChatWidget } from './SupportChatWidget'

// When the cart drawer is open, shift the whole page left by the drawer width
// (on wide screens) so the drawer occupies a right rail and never overlaps the
// products — the store reflows beside it, like the category sidebar.
export function AppShell() {
  const { isDrawerOpen } = useCartUI()
  const { user } = useAuth()
  const location = useLocation()
  // The full-page support view owns the conversation there; hide the floating
  // widget on it so the user never sees two chat UIs at once.
  const onSupportPage = location.pathname === '/me/support'
  return (
    <div
      className={`transition-[padding] duration-300 ${
        isDrawerOpen ? 'lg:pr-[28rem]' : ''
      }`}
    >
      <Header />
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/product/:slug" element={<ProductDetail />} />
        <Route path="/cart" element={<CartPage />} />
        <Route path="/checkout" element={<CheckoutPage />} />
        <Route path="/order-success/:id" element={<OrderSuccessPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/me/support" element={<UserSupportPage />} />
        <Route path="/support/admin" element={<AdminSupportPage />} />
      </Routes>
      {/* Support chat is for customers only (staff have the admin console), and
          is hidden on the dedicated full-page view. */}
      {user && !user.is_staff && !onSupportPage && <SupportChatWidget />}
    </div>
  )
}
