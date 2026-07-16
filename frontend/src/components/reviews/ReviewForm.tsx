import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getGetMyReviewsQueryKey } from '../../api/generated/accounts/accounts'
import { getGetProductQueryKey } from '../../api/generated/catalog/catalog'
import {
  createReview,
  getGetProductReviewsQueryKey,
} from '../../api/generated/reviews/reviews'
import { StarRating } from './StarRating'

export function ReviewForm({
  productId,
  slug,
  existing,
}: {
  productId: number
  slug: string
  existing?: { rating: number; text: string }
}) {
  const queryClient = useQueryClient()
  const [rating, setRating] = useState(existing?.rating ?? 0)
  const [text, setText] = useState(existing?.text ?? '')
  const [needsSupport, setNeedsSupport] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (rating < 1) {
      setError('Поставте оцінку')
      return
    }
    setError(null)
    setBusy(true)
    try {
      await createReview(productId, { rating, text, needs_support: needsSupport })
      // Refresh the list, the product (its average changed), and my-reviews.
      queryClient.invalidateQueries({ queryKey: getGetProductReviewsQueryKey(productId) })
      queryClient.invalidateQueries({ queryKey: getGetProductQueryKey(slug) })
      queryClient.invalidateQueries({ queryKey: getGetMyReviewsQueryKey() })
    } catch {
      setError('Не вдалося зберегти відгук')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-gray-200 p-4">
      <p className="mb-2 text-sm font-semibold text-gray-900">
        {existing ? 'Ваш відгук' : 'Залишити відгук'}
      </p>
      <StarRating value={rating} onChange={setRating} size={28} />
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        placeholder="Поділіться враженнями про товар…"
        className="mt-3 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
      />
      <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={needsSupport}
          onChange={(e) => setNeedsSupport(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-gray-500"
        />
        Потребує відповіді підтримки
      </label>
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={busy}
        className="mt-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-700 disabled:opacity-60"
      >
        {busy ? 'Збереження…' : existing ? 'Оновити відгук' : 'Надіслати відгук'}
      </button>
    </form>
  )
}
