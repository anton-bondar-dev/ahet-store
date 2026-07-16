import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  CartUIContext,
  type CartUIContextValue,
} from '../hooks/useCartUI'

// UI-only state (not server data): the mini-cart drawer's open/closed flag,
// shared between the Header trigger and the CartDrawer consumer. Persisted so
// the drawer stays open across navigation and only closes via its X.
function readOpen(): boolean {
  try {
    return sessionStorage.getItem('cart-drawer-open') === '1'
  } catch {
    return false
  }
}

export function CartUIProvider({ children }: { children: ReactNode }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(readOpen)

  useEffect(() => {
    try {
      sessionStorage.setItem('cart-drawer-open', isDrawerOpen ? '1' : '0')
    } catch {
      /* storage unavailable */
    }
  }, [isDrawerOpen])

  const value = useMemo<CartUIContextValue>(
    () => ({
      isDrawerOpen,
      openDrawer: () => setIsDrawerOpen(true),
      closeDrawer: () => setIsDrawerOpen(false),
    }),
    [isDrawerOpen],
  )

  return <CartUIContext.Provider value={value}>{children}</CartUIContext.Provider>
}
