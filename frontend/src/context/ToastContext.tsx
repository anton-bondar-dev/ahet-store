import { useCallback, useRef, useState, type ReactNode } from 'react'
import { ToastContext } from '../hooks/useToast'

type Toast = { id: number; message: string }

const AUTO_DISMISS_MS = 3500

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  // Monotonic counter for stable keys (no Math.random needed).
  const nextId = useRef(0)

  const showToast = useCallback((message: string) => {
    const id = nextId.current++
    setToasts((prev) => [...prev, { id, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, AUTO_DISMISS_MS)
  }, [])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4"
        aria-live="polite"
        role="status"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="pointer-events-auto max-w-sm animate-toast-in rounded-lg bg-gray-900 px-4 py-2.5 text-center text-sm font-medium text-white shadow-lg"
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
