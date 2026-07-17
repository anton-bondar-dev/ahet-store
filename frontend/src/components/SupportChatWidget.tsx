import { useEffect, useRef, useState } from 'react'
import { useSupportChat } from '../hooks/useSupportChat'
import { UserChatPanel } from './support/UserChatPanel'

// Floating support chat for logged-in customers, available on every page (the
// full-page dashboard view at /me/support hides it to avoid a duplicate UI).
// While closed it keeps polling so a new "ahetStore" reply raises an unread
// badge and plays a subtle sound; opening the panel clears both.
// Persist open state so navigating or an incidental re-render never closes the
// chat — only the launcher / X toggles it.
function readOpen(): boolean {
  try {
    return sessionStorage.getItem('support-chat-open') === '1'
  } catch {
    return false
  }
}

export function SupportChatWidget() {
  const [open, setOpen] = useState(readOpen)

  useEffect(() => {
    try {
      sessionStorage.setItem('support-chat-open', open ? '1' : '0')
    } catch {
      /* storage unavailable */
    }
  }, [open])

  // Poll faster while open, slower in the background while closed.
  const {
    messages,
    isLoading,
    sending,
    send,
    canRate,
    rate,
    status,
    unreadCount,
    endChat,
    ending,
    markRead,
  } = useSupportChat(open ? 4000 : 15000)

  const notifiedIdRef = useRef<number | null>(null) // highest admin id we've chimed for
  const audioRef = useRef<HTMLAudioElement | null>(null)
  // Keep the latest markRead without making it an effect dependency.
  const markReadRef = useRef(markRead)
  markReadRef.current = markRead

  const launcherRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // Close the chat when clicking anywhere outside the panel (the launcher
  // toggles on its own, so it's excluded).
  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      const target = e.target as Node
      if (
        panelRef.current?.contains(target) ||
        launcherRef.current?.contains(target)
      ) {
        return
      }
      setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [open])

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

  // Opening the panel is what marks messages read (persisted server-side), not
  // background polling — so the unread badge survives reloads / other devices.
  useEffect(() => {
    if (open && unreadCount > 0) markReadRef.current().catch(() => {})
  }, [open, unreadCount])

  // Chime once per genuinely new support reply while the panel is closed.
  useEffect(() => {
    const adminIds = messages.filter((m) => m.sender === 'support').map((m) => m.id)
    const maxAdminId = adminIds.length ? Math.max(...adminIds) : 0
    // First load establishes a baseline so pre-existing history never chimes.
    if (notifiedIdRef.current === null) {
      notifiedIdRef.current = maxAdminId
      return
    }
    if (maxAdminId > notifiedIdRef.current) {
      notifiedIdRef.current = maxAdminId
      if (!open) playSound()
    }
  }, [messages, open])

  return (
    <>
      {/* Launcher */}
      <button
        ref={launcherRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Чат підтримки"
        className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-brand text-white shadow-lg transition hover:bg-brand-dark"
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
        {!open && unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-6 min-w-6 items-center justify-center rounded-full bg-white px-1.5 text-xs font-bold text-brand shadow-md ring-2 ring-brand">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Panel */}
      {open && (
        <div
          ref={panelRef}
          className="fixed bottom-24 right-5 z-40 flex h-[28rem] w-[22rem] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl"
        >
          <div className="flex items-center gap-2 border-b border-brand-dark/30 bg-brand px-4 py-3 text-white">
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
            status={status}
            onEnd={endChat}
            ending={ending}
          />
        </div>
      )}
    </>
  )
}
