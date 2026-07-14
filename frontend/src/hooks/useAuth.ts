import { createContext, useContext } from 'react'
import type { AuthResult, UserOut } from '../api/generated/onlineStoreAPI.schemas'

export type AuthContextValue = {
  user: UserOut | null
  isLoading: boolean
  applyAuthed: (result: AuthResult) => void
  login: (username: string, password: string) => Promise<AuthResult>
  register: (
    username: string,
    email: string,
    password: string,
  ) => Promise<AuthResult>
  loginWithGoogle: (credential: string) => Promise<AuthResult>
  logout: () => void
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
