import { useEffect, useRef, useState } from 'react'
import { useSupportChat } from '../hooks/useSupportChat'
import { UserChatPanel } from './support/UserChatPanel'

// Floating support chat for logged-in customers, available on every page (the
// full-page dashboard view at /me/support hides it to avoid a duplicate UI).
// While closed it keeps polling so a new "ahetStore" reply raises an unread
// badge and plays a subtle sound; opening the panel clears both.
export function SupportChatWidget() {
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)

  // Poll faster while open, slower in the background while closed.
  const { messages, isLoading, sending, send, canRate, rate } = useSupportChat(
    open ? 4000 : 15000,
  )

  const seenIdRef = useRef<number | null>(null) // highest msg id the user has seen
  const notifiedIdRef = useRef(0) // highest admin id we've already chimed for
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const playSound = () => {
    try {
      if (!audioRef.current) audioRef.current = new Audio('/sounds/notification.wav')
      audioRef.current.currentTime = 0
      audioRef.current.volume = 0.4
      // Autoplay may be blocked until the user has interacted with the page.
      audioRef.current.play().catch(() => {})
    } catch {
      /* Audio unsupported — badge still works. */
    }
  }

  useEffect(() => {
    const ids = messages.map((m) => m.id)
    const maxId = ids.length ? Math.max(...ids) : 0
    const adminIds = messages.filter((m) => m.sender === 'support').map((m) => m.id)
    const maxAdminId = adminIds.length ? Math.max(...adminIds) : 0

    // First load establishes a baseline so pre-existing history never notifies.
    if (seenIdRef.current === null) {
      seenIdRef.current = maxId
      notifiedIdRef.current = maxAdminId
      return
    }
    // Open → everything on screen counts as seen.
    if (open) {
      seenIdRef.current = maxId
      setUnread(0)
      return
    }
    // Closed → count unseen admin messages; chime once per new arrival.
    const unreadCount = adminIds.filter((id) => id > (seenIdRef.current ?? 0)).length
    setUnread(unreadCount)
    if (maxAdminId > notifiedIdRef.current) {
      notifiedIdRef.current = maxAdminId
      if (unreadCount > 0) playSound()
    }
  }, [messages, open])

  return (
    <>
      {/* Launcher */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Чат підтримки"
        className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-gray-900 text-white shadow-lg transition hover:bg-gray-700"
      >
        {open ? (
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h8M8 8h8m-8 8h5m-9 4 1.5-3A8 8 0 1 1 20 12a8 8 0 0 1-14.5 4.5L4 20Z" />
          </svg>
        )}

        {/* Unread badge (only meaningful while closed) */}
        {!open && unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-6 min-w-6 items-center justify-center rounded-full bg-red-600 px-1.5 text-xs font-bold text-white ring-2 ring-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {/* Panel */}
      {open && (
        <div className="fixed bottom-24 right-5 z-40 flex h-[28rem] w-[22rem] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl">
          <div className="flex items-center gap-2 border-b border-gray-100 bg-gray-900 px-4 py-3 text-white">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/15 text-sm font-bold">
              А
            </span>
            <div>
              <p className="text-sm font-semibold leading-tight">Підтримка ahetStore</p>
              <p className="text-xs text-white/60">Зазвичай відповідаємо швидко</p>
            </div>
          </div>
          <UserChatPanel
            messages={messages}
            isLoading={isLoading}
            sending={sending}
            onSend={send}
            canRate={canRate}
            onRate={rate}
          />
        </div>
      )}
    </>
  )
}
