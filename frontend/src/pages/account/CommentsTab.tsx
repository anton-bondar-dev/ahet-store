import { Link } from 'react-router-dom'
import { useGetMyReviews } from '../../api/generated/accounts/accounts'
import { StarRating } from '../../components/reviews/StarRating'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('uk-UA', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  })
}

export function CommentsTab() {
  const { data, isLoading } = useGetMyReviews()
  const reviews = data?.data ?? []

  return (
    <div>
      <h2 className="mb-5 text-lg font-semibold text-gray-900">Мої відгуки</h2>

      {isLoading ? (
        <p className="text-gray-500">Завантаження…</p>
      ) : reviews.length === 0 ? (
        <div className="flex flex-col items-center rounded-lg border border-dashed border-gray-300 p-12 text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100 text-3xl">
            💬
          </div>
          <p className="max-w-sm text-gray-500">
            Ви ще не залишили жодного відгуку.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-4">
          {reviews.map((review) => (
            <li key={review.id} className="rounded-lg border border-gray-200 p-4">
              <div className="flex items-center justify-between gap-2">
                <Link
                  to={`/product/${review.product_slug}`}
                  className="font-medium text-gray-900 hover:underline"
                >
                  {review.product_title}
                </Link>
                <span className="text-xs text-gray-400">
                  {formatDate(review.created_at)}
                </span>
              </div>
              <div className="mt-1">
                <StarRating value={review.rating} size={16} />
              </div>
              {review.text && (
                <p className="mt-2 whitespace-pre-line text-sm text-gray-600">
                  {review.text}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
