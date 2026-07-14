import { useCallback } from 'react'
import { trackViewed } from '../api/generated/products/products'
import { useAuth } from './useAuth'

const STORAGE_KEY = 'recently-viewed'
const MAX_STORED = 12

export function readLocalViewed(): number[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed)
      ? parsed.filter((n): n is number => typeof n === 'number')
      : []
  } catch {
    return []
  }
}

function writeLocalViewed(ids: number[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids.slice(0, MAX_STORED)))
  } catch {
    /* storage unavailable */
  }
}

export function clearLocalViewed(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

// Records a product view: logged-in → backend upsert; anonymous → localStorage
// (deduped, most-recent-first, capped). Returns a stable `record` callback.
export function useRecentlyViewed() {
  const { user } = useAuth()

  const record = useCallback(
    (productId: number) => {
      if (user) {
        trackViewed({ product_id: productId }).catch(() => {})
        return
      }
      const existing = readLocalViewed().filter((id) => id !== productId)
      writeLocalViewed([productId, ...existing])
    },
    [user],
  )

  return { record }
}
