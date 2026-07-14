import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { GOOGLE_CLIENT_ID } from '../lib/config'
import { loadGoogleIdentity } from '../lib/google'

// Renders the official Google Identity Services button. On credential callback,
// posts the ID token to /api/auth/google via loginWithGoogle. Renders nothing
// if VITE_GOOGLE_CLIENT_ID is not configured.
export function GoogleSignInButton() {
  const navigate = useNavigate()
  const { loginWithGoogle } = useAuth()
  const ref = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !ref.current) return
    let cancelled = false

    loadGoogleIdentity()
      .then(() => {
        if (cancelled || !ref.current || !window.google) return
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => {
            loginWithGoogle(response.credential)
              .then(() => navigate('/'))
              .catch(() => setError('Не вдалося увійти через Google'))
          },
        })
        window.google.accounts.id.renderButton(ref.current, {
          theme: 'outline',
          size: 'large',
          width: 320,
          text: 'continue_with',
          locale: 'uk',
        })
      })
      .catch(() => setError('Не вдалося завантажити Google'))

    return () => {
      cancelled = true
    }
  }, [loginWithGoogle, navigate])

  if (!GOOGLE_CLIENT_ID) return null

  return (
    <div className="flex flex-col items-center gap-2">
      <div ref={ref} />
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
