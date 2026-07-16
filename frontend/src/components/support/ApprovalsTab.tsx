import { useQueryClient } from '@tanstack/react-query'
import {
  getListApprovalsQueryKey,
  useApproveAction,
  useListApprovals,
  useRejectAction,
} from '../../api/generated/support/support'

// The Team Lead's mini-list: bonus/coupon gifts an operator requested that
// exceed their auto-approve threshold, awaiting approval or rejection.
export function ApprovalsTab() {
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: getListApprovalsQueryKey() })
  const { data, isLoading } = useListApprovals({ query: { refetchInterval: 8000 } })
  const approve = useApproveAction({ mutation: { onSuccess: invalidate } })
  const reject = useRejectAction({ mutation: { onSuccess: invalidate } })
  const rows = data?.data ?? []

  if (isLoading) return <p className="text-sm text-gray-400">Завантаження…</p>
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center text-sm text-gray-400">
        Немає запитів на підтвердження 🎉
      </div>
    )
  }

  return (
    <ul className="flex flex-col gap-3">
      {rows.map((a) => (
        <li key={a.id} className="flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50/50 p-4">
          <div className="min-w-0 text-sm">
            <p className="font-medium text-gray-900">
              {a.action_type === 'grant_bonuses'
                ? `Нарахувати ${a.amount} бонусів`
                : `Промокод на ${a.percent}%`}
            </p>
            <p className="text-xs text-gray-500">
              Запит від <strong>{a.requested_by}</strong> · клієнт {a.customer_name}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() => approve.mutate({ approvalId: a.id })}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-700"
            >
              Підтвердити
            </button>
            <button
              type="button"
              onClick={() => reject.mutate({ approvalId: a.id })}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:bg-gray-50"
            >
              Відхилити
            </button>
          </div>
        </li>
      ))}
    </ul>
  )
}
