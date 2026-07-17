// Pull a human-readable message out of a django-ninja error response.
// HttpError → { detail: "..." }; validation error → { detail: [{ msg, ... }] }.
export function apiErrorMessage(err: unknown): string | null {
  const detail = (
    err as { response?: { data?: { detail?: unknown } } }
  )?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) =>
        d && typeof d === 'object' && 'msg' in d
          ? String((d as { msg: unknown }).msg)
          : String(d),
      )
      .join(' ')
  }
  return null
}
