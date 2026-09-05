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
import { useAuth } from './useAuth'
import { useToast } from './useToast'
import { apiErrorMessage } from '../lib/apiError'

// Single source of truth for the cart: the React Query cache. Every consumer
// (header badge, drawer, cart page) shares one query key, so writing each
// mutation's response into the cache keeps the whole app in sync — no Context.
export function useCart() {
  const queryClient = useQueryClient()
  // The access token only lives in memory, so on a page load it is restored
  // asynchronously. /api/cart answers anonymous callers with 200 and an empty
  // cart, so a request that races that restore would cache the empty anonymous
  // cart and never retry (no 401 for the interceptor to catch) — the shopper
  // would see "Кошик (0)" until the next mutation. Wait for auth to settle.
  const { isLoading: authLoading } = useAuth()
  const cartQuery = useGetCart({ query: { enabled: !authLoading } })

  const { showToast } = useToast()

  const onSuccess = (response: AxiosResponse<CartOut>) => {
    queryClient.setQueryData(getGetCartQueryKey(), response)
  }
  // Cart writes used to fail silently (unhandled rejection, no UI feedback) —
  // surface the server's message so the shopper knows what happened.
  const onError = (err: unknown) =>
    showToast(apiErrorMessage(err) ?? 'Не вдалося оновити кошик. Спробуйте ще раз.')

  const addMutation = useAddToCart({ mutation: { onSuccess, onError } })
  const updateMutation = useUpdateCartItem({ mutation: { onSuccess, onError } })
  const deleteMutation = useDeleteCartItem({ mutation: { onSuccess, onError } })

  const cart = cartQuery.data?.data
  // Consumers need this: `items` defaults to [] while the cart is still in
  // flight, so without it every page paints its "cart is empty" state first.
  const isLoading = authLoading || cartQuery.isPending
  const items = cart?.items ?? []
  const totalQuantity = cart?.total_quantity ?? 0
  const totalPrice = cart?.total_price ?? '0.00'

  return {
    cart,
    isLoading,
    items,
    totalQuantity,
    totalPrice,
    addToCart: (productId: number, quantity = 1) =>
      addMutation.mutateAsync({ data: { product_id: productId, quantity } }),
    updateQuantity: (itemId: number, quantity: number) =>
      updateMutation.mutateAsync({ itemId, data: { quantity } }).catch(() => {}),
    removeItem: (itemId: number) =>
      deleteMutation.mutateAsync({ itemId }).catch(() => {}),
    isAdding: addMutation.isPending,
  }
}
