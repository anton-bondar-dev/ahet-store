import { createContext, useContext } from 'react'

export type CartUIContextValue = {
  isDrawerOpen: boolean
  openDrawer: () => void
  closeDrawer: () => void
}

export const CartUIContext = createContext<CartUIContextValue | null>(null)

export function useCartUI(): CartUIContextValue {
  const ctx = useContext(CartUIContext)
  if (!ctx) throw new Error('useCartUI must be used within a CartUIProvider')
  return ctx
}
