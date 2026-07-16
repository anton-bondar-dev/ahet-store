import { Link } from 'react-router-dom'
import { useGetMyReviews } from '../../api/generated/accounts/accounts'
import { useGetProductReviews } from '../../api/generated/reviews/reviews'
import { useAuth } from '../../hooks/useAuth'
import { useIsStaff } from '../../hooks/useIsStaff'
import { ReviewCard } from './ReviewCard'
import { ReviewForm } from './ReviewForm'
import { StarRating } from './StarRating'

export function ReviewsSection({
  productId,
  slug,
  averageRating,
  reviewsCount,
}: {
  productId: number
  slug: string
  averageRating: number
  reviewsCount: number
}) {
  const { user } = useAuth()
  const isStaff = useIsStaff()
  const { data } = useGetProductReviews(productId)
  const reviews = data?.data ?? []

  // The caller's own review for this product (reliable, from the auth'd endpoint).
  const { data: mine } = useGetMyReviews({ query: { enabled: !!user } })
  const myReview = mine?.data?.find((r) => r.product_slug === slug)

  return (
    <section className="mt-10 border-t border-gray-100 pt-8">
      <h2 className="text-xl font-bold text-gray-900">Відгуки покупців</h2>

      <div className="mt-2 flex items-center gap-3">
        <StarRating value={averageRating} size={22} />
        <span className="text-lg font-semibold text-gray-900">
          {averageRating.toFixed(1)}
        </span>
        <span className="text-sm text-gray-500">{reviewsCount} відгуків</span>
      </div>

      <div className="mt-6">
        {isStaff ? (
          // Staff don't author reviews — they answer them via the reply action.
          <p className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
            Ви можете відповідати на відгуки як представник підтримки.
          </p>
        ) : user ? (
          <ReviewForm productId={productId} slug={slug} existing={myReview} />
        ) : (
          <p className="rounded-lg border border-gray-200 p-4 text-sm text-gray-500">
            <Link to="/login" className="font-medium text-gray-900 hover:underline">
              Увійдіть
            </Link>
            , щоб залишити відгук.
          </p>
        )}
      </div>

      <div className="mt-4">
        {reviews.length === 0 ? (
          <p className="py-6 text-sm text-gray-500">
            Ще немає відгуків. Будьте першим!
          </p>
        ) : (
          reviews.map((review) => (
            <ReviewCard key={review.id} review={review} productId={productId} />
          ))
        )}
      </div>
    </section>
  )
}
