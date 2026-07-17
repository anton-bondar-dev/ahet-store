import { createContext, useContext } from 'react'

// Trending-score cutoffs for the staff-only 🔥/🧊 catalog badges. Defaults are
// no-op (no product qualifies) until the grid computes real percentiles.
export const TrendingContext = createContext<{ hot: number; cold: number }>({
  hot: Number.POSITIVE_INFINITY,
  cold: Number.NEGATIVE_INFINITY,
})

export const useTrending = () => useContext(TrendingContext)
