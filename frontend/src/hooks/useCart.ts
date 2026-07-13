import { useQueryClient } from '@tanstack/react-query'
import type { AxiosResponse } from 'axios'
import {
  getGetCartQueryKey,
  useAddToCart,
  useDeleteCartItem,
  useGetCart,
  useUpdateCartItem,
} from '../api/generated/cart/cart'
import type { CartOut } from '../api/generated/onlineStoreAPI.schemas'

// Single source of truth for the cart: the React Query cache. Every consumer
// (header badge, drawer, cart page) shares one query key, so writing each
// mutation's response into the cache keeps the whole app in sync — no Context.
export function useCart() {
  const queryClient = useQueryClient()
  const cartQuery = useGetCart()

  const onSuccess = (response: AxiosResponse<CartOut>) => {
    queryClient.setQueryData(getGetCartQueryKey(), response)
  }

  const addMutation = useAddToCart({ mutation: { onSuccess } })
  const updateMutation = useUpdateCartItem({ mutation: { onSuccess } })
  const deleteMutation = useDeleteCartItem({ mutation: { onSuccess } })

  const cart = cartQuery.data?.data
  const items = cart?.items ?? []
  const totalQuantity = cart?.total_quantity ?? 0
  const totalPrice = cart?.total_price ?? '0.00'

  return {
    cart,
    items,
    totalQuantity,
    totalPrice,
    addToCart: (productId: number, quantity = 1) =>
      addMutation.mutateAsync({ data: { product_id: productId, quantity } }),
    updateQuantity: (itemId: number, quantity: number) =>
      updateMutation.mutateAsync({ itemId, data: { quantity } }),
    removeItem: (itemId: number) => deleteMutation.mutateAsync({ itemId }),
    isAdding: addMutation.isPending,
  }
}
