import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  googleAuth,
  login as loginApi,
  me,
  register as registerApi,
} from '../api/generated/auth/auth'
import { getGetCartQueryKey } from '../api/generated/cart/cart'
import { trackViewed } from '../api/generated/products/products'
import type { AuthResult, UserOut } from '../api/generated/onlineStoreAPI.schemas'
import {
  clearAuth,
  getRefreshToken,
  registerAuthClearedHandler,
  setTokens,
} from '../lib/authToken'
import { AuthContext, type AuthContextValue } from '../hooks/useAuth'
import { clearLocalViewed, readLocalViewed } from '../hooks/useRecentlyViewed'

// Push any anonymous viewed-history into the account on sign-in, then clear it.
function syncLocalViewed() {
  const ids = readLocalViewed()
  if (ids.length === 0) return
  // Oldest first so the most-recent local view ends up newest server-side.
  Promise.allSettled(
    [...ids].reverse().map((id) => trackViewed({ product_id: id })),
  ).finally(() => clearLocalViewed())
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<UserOut | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const invalidateCart = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: getGetCartQueryKey() })
  }, [queryClient])

  // Store tokens + user, refresh the cart (it may have just been merged), and
  // sync any anonymous viewed-history into the account.
  const applyAuthed = useCallback(
    (result: AuthResult) => {
      setTokens(result.access ?? null, result.refresh ?? null)
      setUser(result.user ?? null)
      invalidateCart()
      if (result.status === 'authed') syncLocalViewed()
    },
    [invalidateCart],
  )

  const logout = useCallback(() => {
    clearAuth()
    setUser(null)
    invalidateCart()
  }, [invalidateCart])

  // A failed silent refresh (from the axios interceptor) resets React state.
  useEffect(() => {
    registerAuthClearedHandler(() => setUser(null))
  }, [])

  // Rehydrate on load: if a refresh token exists, `me()` triggers a silent
  // refresh through the interceptor and returns the current user.
  useEffect(() => {
    let active = true
    if (!getRefreshToken()) {
      setIsLoading(false)
      return
    }
    me()
      .then((res) => {
        if (active) setUser(res.data)
      })
      .catch(() => {
        if (active) {
          clearAuth()
          setUser(null)
        }
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await loginApi({ email, password })
      if (res.data.status === 'authed') applyAuthed(res.data)
      return res.data
    },
    [applyAuthed],
  )

  const register = useCallback(
    async (name: string, email: string, password: string) => {
      const res = await registerApi({ name, email, password })
      if (res.data.status === 'authed') applyAuthed(res.data)
      return res.data
    },
    [applyAuthed],
  )

  const loginWithGoogle = useCallback(
    async (credential: string) => {
      const res = await googleAuth({ credential })
      if (res.data.status === 'authed') applyAuthed(res.data)
      return res.data
    },
    [applyAuthed],
  )

  const refreshUser = useCallback(async () => {
    try {
      const res = await me()
      setUser(res.data)
    } catch {
      /* leave current user state as-is */
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      applyAuthed,
      login,
      register,
      loginWithGoogle,
      logout,
      refreshUser,
    }),
    [user, isLoading, applyAuthed, login, register, loginWithGoogle, logout, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
