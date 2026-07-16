// Display titles for support staff. The Owner (superuser) is the Team Lead; a
// plain staff account is a Support Operator. Returns null for regular customers.
export function roleLabel(user: { is_superuser?: boolean; is_staff?: boolean } | null): string | null {
  if (!user) return null
  if (user.is_superuser) return 'Тімлід підтримки'
  if (user.is_staff) return 'Оператор підтримки'
  return null
}
