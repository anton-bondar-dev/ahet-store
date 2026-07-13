import { useMemo, useState, type ReactNode } from 'react'
import {
  CartUIContext,
  type CartUIContextValue,
} from '../hooks/useCartUI'

// UI-only state (not server data): the mini-cart drawer's open/closed flag,
// shared between the Header trigger and the CartDrawer consumer.
export function CartUIProvider({ children }: { children: ReactNode }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)

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
