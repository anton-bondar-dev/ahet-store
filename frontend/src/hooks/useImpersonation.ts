import { useEffect, useState } from 'react'
import { getImpersonationName, onImpersonationChange } from '../lib/impersonation'

// Reactive view of the current impersonation state (name of the customer being
// viewed, or null). Backed by the sessionStorage-based impersonation module.
export function useImpersonation(): { name: string | null; active: boolean } {
  const [name, setName] = useState<string | null>(getImpersonationName())
  useEffect(() => onImpersonationChange(() => setName(getImpersonationName())), [])
  return { name, active: !!name }
}
