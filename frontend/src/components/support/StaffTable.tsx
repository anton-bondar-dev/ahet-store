import { useQueryClient } from '@tanstack/react-query'
import {
  getListStaffQueryKey,
  useBlockStaff,
  useListStaff,
  useUnblockStaff,
} from '../../api/generated/support/support'

// Owner-only roster of support staff with mini-dossiers (role, rating, volume)
// and block/unblock controls.
export function StaffTable() {
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: getListStaffQueryKey() })
  const { data, isLoading } = useListStaff({ query: { refetchInterval: 10000 } })
  const block = useBlockStaff({ mutation: { onSuccess: invalidate } })
  const unblock = useUnblockStaff({ mutation: { onSuccess: invalidate } })
  const rows = data?.data ?? []

  if (isLoading) return <p className="text-sm text-gray-400">Завантаження…</p>

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
          <tr>
            <th className="px-4 py-2">Оператор</th>
            <th className="px-4 py-2">Роль</th>
            <th className="px-4 py-2">Доступність</th>
            <th className="px-4 py-2">Закрито</th>
            <th className="px-4 py-2">Коментарі</th>
            <th className="px-4 py-2">Рейтинг</th>
            <th className="px-4 py-2">Статус</th>
            <th className="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((s) => (
            <tr key={s.id} className={s.is_active ? '' : 'bg-red-50/40'}>
              <td className="px-4 py-2">
                <span className="font-medium text-gray-900">{s.name}</span>
                <span className="ml-1 text-xs text-gray-400">@{s.username}</span>
              </td>
              <td className="px-4 py-2 text-gray-600">
                {s.role === 'owner' ? 'Тімлід' : 'Оператор'}
              </td>
              <td className="px-4 py-2">
                <span className={`inline-flex items-center gap-1 text-xs ${s.status === 'away' ? 'text-gray-400' : 'text-emerald-600'}`}>
                  <span className={`h-2 w-2 rounded-full ${s.status === 'away' ? 'bg-gray-300' : 'bg-emerald-500'}`} />
                  {s.status === 'away' ? 'Відійшов' : 'Онлайн'}
                </span>
              </td>
              <td className="px-4 py-2 text-gray-700">{s.resolved_tickets}</td>
              <td className="px-4 py-2 text-gray-700">{s.comments_resolved}</td>
              <td className="px-4 py-2 text-gray-700">
                {s.positive_rate == null ? '—' : `${s.positive_rate}%`}
                <span className="ml-1 text-xs text-gray-400">({s.ratings_total})</span>
              </td>
              <td className="px-4 py-2">
                {s.is_active ? (
                  <span className="text-emerald-600">Активний</span>
                ) : (
                  <span className="font-medium text-red-600">Заблокований</span>
                )}
              </td>
              <td className="px-4 py-2 text-right">
                {s.role !== 'owner' &&
                  (s.is_active ? (
                    <button
                      type="button"
                      onClick={() => block.mutate({ userId: s.id })}
                      className="rounded-md border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 transition hover:bg-red-50"
                    >
                      Заблокувати
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => unblock.mutate({ userId: s.id })}
                      className="rounded-md border border-gray-200 px-2.5 py-1 text-xs font-medium text-gray-600 transition hover:bg-gray-50"
                    >
                      Розблокувати
                    </button>
                  ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
