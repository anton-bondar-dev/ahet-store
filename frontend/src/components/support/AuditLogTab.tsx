import { useListAuditLog } from '../../api/generated/support/support'
import type { AuditLogOut } from '../../api/generated/onlineStoreAPI.schemas'

// Owner-only (superuser) history of powerful staff actions.
const ACTION_LABELS: Record<string, string> = {
  impersonate_start: 'Почав перегляд від імені',
  impersonate_end: 'Завершив перегляд від імені',
  tag_add: 'Додав тег',
  tag_remove: 'Прибрав тег',
  grant_bonuses: 'Нарахував бонуси',
  cancel_bonuses: 'Скасував бонуси',
  generate_coupon: 'Згенерував промокод',
  close_ticket: 'Закрив звернення',
  block_user: 'Заблокував клієнта',
  unblock_user: 'Розблокував клієнта',
  block_staff: 'Заблокував оператора',
  unblock_staff: 'Розблокував оператора',
}

function summarize(a: AuditLogOut): string {
  const m = a.meta || {}
  if (a.action_type === 'grant_bonuses') return `${m.amount} бонусів`
  if (a.action_type === 'generate_coupon') return `${m.code} (${m.percent}%)`
  if (a.action_type === 'tag_add' || a.action_type === 'tag_remove') return String(m.tag ?? '')
  return ''
}

export function AuditLogTab() {
  const { data, isLoading } = useListAuditLog({ query: { refetchInterval: 10000 } })
  const rows = data?.data ?? []

  if (isLoading) return <p className="text-sm text-gray-400">Завантаження…</p>
  if (rows.length === 0) {
    return <p className="text-sm text-gray-400">Журнал порожній</p>
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
          <tr>
            <th className="px-4 py-2">Час</th>
            <th className="px-4 py-2">Адмін</th>
            <th className="px-4 py-2">Дія</th>
            <th className="px-4 py-2">Клієнт</th>
            <th className="px-4 py-2">Деталі</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((a) => (
            <tr key={a.id}>
              <td className="whitespace-nowrap px-4 py-2 text-xs text-gray-500">
                {new Date(a.created_at).toLocaleString('uk-UA')}
              </td>
              <td className="px-4 py-2 font-medium text-gray-900">{a.admin_username}</td>
              <td className="px-4 py-2 text-gray-700">{ACTION_LABELS[a.action_type] ?? a.action_type}</td>
              <td className="px-4 py-2 text-gray-500">{a.target_username ?? '—'}</td>
              <td className="px-4 py-2 text-gray-500">{summarize(a)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
