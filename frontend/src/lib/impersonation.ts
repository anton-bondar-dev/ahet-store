// Impersonation ("view as customer") state. The scoped storefront token lives
// in sessionStorage (tab-scoped, cleared on tab close) so it never leaks into
// the persisted refresh token, and the axios interceptor prefers it when set.
// A custom event lets React components react to enter/exit.
const TOKEN_KEY = 'imp-token'
const NAME_KEY = 'imp-name'
const EVENT = 'impersonation-change'

export function getImpersonationToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function getImpersonationName(): string | null {
  try {
    return sessionStorage.getItem(NAME_KEY)
  } catch {
    return null
  }
}

export function startImpersonation(token: string, name: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
    sessionStorage.setItem(NAME_KEY, name)
    window.dispatchEvent(new Event(EVENT))
  } catch {
    /* storage unavailable */
  }
}

export function stopImpersonation(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(NAME_KEY)
    window.dispatchEvent(new Event(EVENT))
  } catch {
    /* storage unavailable */
  }
}

export function onImpersonationChange(fn: () => void): () => void {
  window.addEventListener(EVENT, fn)
  return () => window.removeEventListener(EVENT, fn)
}
