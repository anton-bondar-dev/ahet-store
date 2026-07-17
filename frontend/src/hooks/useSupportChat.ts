import { useQueryClient } from '@tanstack/react-query'
import {
  getGetMyChatQueryKey,
  useCloseMyChat,
  useGetMyChat,
  useMarkMyChatRead,
  useRateSupport,
  useSendMyMessage,
} from '../api/generated/support/support'

// Shared customer-side chat state. Both the floating widget and the full-page
// dashboard view use this, so they read/write the same React Query cache entry
// and stay in sync. `refetchInterval` lets each caller poll at its own cadence
// (e.g. slower when the widget is closed, faster when a view is focused).
export function useSupportChat(refetchInterval: number | false = false) {
  const queryClient = useQueryClient()

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: getGetMyChatQueryKey() })

  const chatQuery = useGetMyChat({ query: { refetchInterval } })
  const sendMutation = useSendMyMessage({ mutation: { onSuccess: invalidate } })
  const rateMutation = useRateSupport({ mutation: { onSuccess: invalidate } })
  const closeMutation = useCloseMyChat({ mutation: { onSuccess: invalidate } })
  const readMutation = useMarkMyChatRead({ mutation: { onSuccess: invalidate } })

  const data = chatQuery.data?.data

  return {
    messages: data?.messages ?? [],
    // "none" (no ticket yet) | "open" | "closed".
    status: data?.status ?? 'none',
    // Server-tracked unread support replies — survives reloads / other devices.
    unreadCount: data?.unread_count ?? 0,
    isLoading: chatQuery.isLoading,
    sending: sendMutation.isPending,
    send: (text: string) => sendMutation.mutateAsync({ data: { text } }),
    // The ticket is closed and awaiting the user's end-of-chat 👍/👎.
    canRate: data?.can_rate ?? false,
    rate: (isPositive: boolean) =>
      rateMutation.mutateAsync({ data: { is_positive: isPositive } }),
    // The customer ends their own conversation (then can rate it).
    endChat: () => closeMutation.mutateAsync(),
    ending: closeMutation.isPending,
    // Clears the unread badge — call only when the user actually views the chat.
    markRead: () => readMutation.mutateAsync(),
  }
}
