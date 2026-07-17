import { useQueryClient } from '@tanstack/react-query'
import type { AxiosResponse } from 'axios'
import {
  getListWishlistIdsQueryKey,
  getListWishlistQueryKey,
  useListWishlistIds,
  useToggleWishlist,
} from '../api/generated/wishlist/wishlist'
import { useAuth } from './useAuth'

type IdsResponse = AxiosResponse<number[]>

// Wishlist state + optimistic toggle. The id-only list (`/wishlist/ids`) is the
// single source of truth for heart state across every product card; the toggle
// mutation flips it instantly (optimistic) and reconciles with the server.
export function useWishlist() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  // Only shoppers have a wishlist — don't fetch for anonymous users or staff.
  const enabled = !!user && !user.is_staff
  const idsQuery = useListWishlistIds({ query: { enabled } })
  const ids = idsQuery.data?.data ?? []

  const idsKey = getListWishlistIdsQueryKey()

  const toggleMutation = useToggleWishlist({
    mutation: {
      onMutate: async ({ productId }) => {
        // Cancel in-flight refetches so they don't clobber the optimistic flip.
        await queryClient.cancelQueries({ queryKey: idsKey })
        const previous = queryClient.getQueryData<IdsResponse>(idsKey)
        queryClient.setQueryData<IdsResponse>(idsKey, (old) => {
          if (!old) return old
          const list = old.data ?? []
          const next = list.includes(productId)
            ? list.filter((id) => id !== productId)
            : [...list, productId]
          return { ...old, data: next }
        })
        return { previous }
      },
      onError: (_err, _vars, context) => {
        const ctx = context as { previous?: IdsResponse } | undefined
        if (ctx?.previous) queryClient.setQueryData(idsKey, ctx.previous)
      },
      onSettled: () => {
        // Reconcile the heart state and the full wishlist page with the server.
        queryClient.invalidateQueries({ queryKey: idsKey })
        queryClient.invalidateQueries({ queryKey: getListWishlistQueryKey() })
      },
    },
  })

  return {
    ids,
    count: ids.length,
    isEnabled: enabled,
    isFavorite: (productId: number) => ids.includes(productId),
    toggle: (productId: number) => toggleMutation.mutate({ productId }),
  }
}
