import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'search-history'
const MAX_STORED = 10

function readHistory(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === 'string')
      : []
  } catch {
    return []
  }
}

// Manages the user's recent searches, persisted to localStorage.
export function useSearchHistory() {
  const [history, setHistory] = useState<string[]>(readHistory)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
    } catch {
      /* storage unavailable — ignore */
    }
  }, [history])

  const addSearch = useCallback((query: string) => {
    const trimmed = query.trim()
    if (!trimmed) return
    setHistory((prev) => {
      const withoutDupe = prev.filter(
        (item) => item.toLowerCase() !== trimmed.toLowerCase(),
      )
      return [trimmed, ...withoutDupe].slice(0, MAX_STORED)
    })
  }, [])

  const removeSearch = useCallback((query: string) => {
    setHistory((prev) =>
      prev.filter((item) => item.toLowerCase() !== query.toLowerCase()),
    )
  }, [])

  const clearHistory = useCallback(() => setHistory([]), [])

  return { history, addSearch, removeSearch, clearHistory }
}
