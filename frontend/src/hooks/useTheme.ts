import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

// Read the current theme: an explicit user choice (localStorage) wins, else the
// OS preference. Mirrors the inline <head> script that sets data-theme pre-paint.
function readTheme(): Theme {
  try {
    const stored = localStorage.getItem('theme')
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    /* storage unavailable */
  }
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light'
  } catch {
    return 'light'
  }
}

// Light/dark theme with a persisted toggle. Applies `data-theme` to <html>,
// which the CSS uses to remap the palette.
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('theme', theme)
    } catch {
      /* storage unavailable */
    }
  }, [theme])

  const toggle = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

  return { theme, toggle }
}
