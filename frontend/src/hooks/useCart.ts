import { useQueryClient } from '@tanstack/react-query'
import {
  getGetCartQueryKey,
  useAddToCart,
  useGetCart,
} from '../api/generated/cart/cart'

// Single source of truth for the cart: the React Query cache. Every consumer
// (header badge, product page, cart page) shares one query key, so writing the
// mutation's response into the cache keeps the whole app in sync — no Context.
export function useCart() {
  const queryClient = useQueryClient()
  const cartQuery = useGetCart()

  const addMutation = useAddToCart({
    mutation: {
      onSuccess: (response) => {
        queryClient.setQueryData(getGetCartQueryKey(), response)
      },
    },
  })

  const cart = cartQuery.data?.data
  const totalQuantity = cart?.total_quantity ?? 0

  const addToCart = (productId: number, quantity = 1) =>
    addMutation.mutateAsync({ data: { product_id: productId, quantity } })

  return {
    cart,
    totalQuantity,
    addToCart,
    isAdding: addMutation.isPending,
  }
}
