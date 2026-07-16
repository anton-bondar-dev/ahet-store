import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  getGetTicketQueryKey,
  useAssignTag,
  useBlockUser,
  useListTags,
  useRemoveTag,
  useTicketCustomerOrders,
  useUnblockUser,
} from '../../api/generated/support/support'
import type { CustomerTagOut } from '../../api/generated/onlineStoreAPI.schemas'
import { formatPrice } from '../../lib/format'

const ORDER_STATUS_LABELS: Record<string, string> = {
  new: 'Новий',
  processing: 'Обробка',
  shipped: 'Відправлено',
  delivered: 'Доставлено',
  cancelled: 'Скасовано',
}

// Staff-only context beside the conversation: customer karma tags (add/remove
// from the shared vocabulary) + recent orders, so the agent has full context.
export function CustomerContext({
  ticketId,
  userId,
  tags,
  isOwner = false,
  blocked = false,
}: {
  ticketId: number
  userId: number
  tags: CustomerTagOut[]
  isOwner?: boolean
  blocked?: boolean
}) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useTicketCustomerOrders(ticketId)
  const orders = data?.data ?? []

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: getGetTicketQueryKey(ticketId) })
  const vocab = useListTags()
  const assign = useAssignTag({ mutation: { onSuccess: invalidate } })
  const remove = useRemoveTag({ mutation: { onSuccess: invalidate } })
  const blockUser = useBlockUser({ mutation: { onSuccess: invalidate } })
  const unblockUser = useUnblockUser({ mutation: { onSuccess: invalidate } })

  const [picking, setPicking] = useState(false)
  const assignedIds = new Set(tags.map((t) => t.id))
  const available = (vocab.data?.data ?? []).filter((t) => !assignedIds.has(t.id))

  return (
    <aside className="space-y-4">
      {blocked && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">
          🚫 Клієнта заблоковано
        </div>
      )}
      {/* Karma tags */}
      <div className="rounded-lg border border-gray-200 p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Теги клієнта</p>
        <div className="flex flex-wrap gap-1.5">
          {tags.map((t) => (
            <span
              key={t.id}
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold text-white"
              style={{ backgroundColor: t.color }}
            >
              {t.label}
              <button
                type="button"
                onClick={() => remove.mutate({ userId, tagId: t.id })}
                aria-label={`Прибрати ${t.label}`}
                className="opacity-80 hover:opacity-100"
              >
                ×
              </button>
            </span>
          ))}
          <button
            type="button"
            onClick={() => setPicking((v) => !v)}
            className="rounded-full border border-dashed border-gray-300 px-2 py-0.5 text-xs text-gray-500 hover:bg-gray-50"
          >
            + тег
          </button>
        </div>
        {picking && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {available.length === 0 ? (
              <span className="text-xs text-gray-400">Немає доступних тегів</span>
            ) : (
              available.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => {
                    assign.mutate({ userId, data: { tag_id: t.id } })
                    setPicking(false)
                  }}
                  className="rounded-full px-2 py-0.5 text-xs font-medium text-white"
                  style={{ backgroundColor: t.color }}
                >
                  {t.label}
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {/* Recent orders */}
      <div className="rounded-lg border border-gray-200 p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Останні замовлення</p>
        {isLoading ? (
          <p className="text-sm text-gray-400">Завантаження…</p>
        ) : orders.length === 0 ? (
          <p className="text-sm text-gray-400">Замовлень немає</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {orders.map((o) => (
              <li key={o.id} className="rounded-md bg-gray-50 px-3 py-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900">№{o.id}</span>
                  <span className="text-xs text-gray-500">
                    {ORDER_STATUS_LABELS[o.status] ?? o.status}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>{o.item_count} тов.</span>
                  <span>{formatPrice(o.total_price)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Moderation (Owner only) */}
      {isOwner && (
        <div className="rounded-lg border border-gray-200 p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Модерація</p>
          {blocked ? (
            <button
              type="button"
              onClick={() => unblockUser.mutate({ userId })}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50"
            >
              Розблокувати клієнта
            </button>
          ) : (
            <div className="flex flex-col gap-1.5">
              <button
                type="button"
                onClick={() => blockUser.mutate({ userId, data: { permanent: false, days: 7 } })}
                className="w-full rounded-md border border-amber-300 px-3 py-1.5 text-xs font-medium text-amber-700 transition hover:bg-amber-50"
              >
                Заблокувати на 7 днів
              </button>
              <button
                type="button"
                onClick={() => blockUser.mutate({ userId, data: { permanent: true, days: 0 } })}
                className="w-full rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium text-red-700 transition hover:bg-red-50"
              >
                Заблокувати назавжди
              </button>
            </div>
          )}
        </div>
      )}
    </aside>
  )
}
