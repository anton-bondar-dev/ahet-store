// Access token lives in memory; refresh token is persisted so a page reload
// can silently re-authenticate. Kept outside React so the axios interceptors
// (which aren't React components) can read/update it.
const REFRESH_KEY = 'auth-refresh'

let accessToken: string | null = null
let onCleared: (() => void) | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY)
  } catch {
    return null
  }
}

export function setRefreshToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(REFRESH_KEY, token)
    else localStorage.removeItem(REFRESH_KEY)
  } catch {
    /* storage unavailable */
  }
}

export function setTokens(access: string | null, refresh?: string | null): void {
  setAccessToken(access)
  if (refresh !== undefined) setRefreshToken(refresh)
}

// AuthContext registers a handler so a failed refresh (session fully expired)
// can reset the React auth state to logged-out.
export function registerAuthClearedHandler(fn: () => void): void {
  onCleared = fn
}

export function clearAuth(): void {
  setAccessToken(null)
  setRefreshToken(null)
  onCleared?.()
}
