import { useAuth } from './useAuth'

// True for support/admin (is_staff) accounts. They are employees, not shoppers:
// the UI hides buyer actions (cart, checkout, reviews, bonuses, customer chat)
// for them — the backend enforces the same rules with 403s.
export function useIsStaff(): boolean {
  const { user } = useAuth()
  return !!user?.is_staff
}
