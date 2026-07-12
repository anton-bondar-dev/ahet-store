const STORAGE_KEY = 'cart-session-id'

let cached: string | null = null

function generateUuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  // Fallback for environments without crypto.randomUUID.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// Returns the anonymous cart session id, creating and persisting it on first use.
export function getSessionId(): string {
  if (cached) return cached
  try {
    const existing = localStorage.getItem(STORAGE_KEY)
    if (existing) {
      cached = existing
      return existing
    }
  } catch {
    /* storage unavailable */
  }
  const id = generateUuid()
  try {
    localStorage.setItem(STORAGE_KEY, id)
  } catch {
    /* storage unavailable */
  }
  cached = id
  return id
}
