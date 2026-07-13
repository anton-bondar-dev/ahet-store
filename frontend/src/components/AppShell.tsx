import { Route, Routes } from 'react-router-dom'
import App from '../App'
import { useCartUI } from '../hooks/useCartUI'
import { CartPage } from '../pages/CartPage'
import { ProductDetail } from '../pages/ProductDetail'
import { Header } from './Header'

// When the cart drawer is open, shift the whole page left by the drawer width
// (on wide screens) so the drawer occupies a right rail and never overlaps the
// products — the store reflows beside it, like the category sidebar.
export function AppShell() {
  const { isDrawerOpen } = useCartUI()
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
      </Routes>
    </div>
  )
}
