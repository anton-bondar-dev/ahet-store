import { createContext, useContext } from 'react'

export type ToastContextValue = {
  // Show a transient notification. Auto-dismisses after a few seconds.
  showToast: (message: string) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}
