import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  createReply,
  getGetProductReviewsQueryKey,
} from '../../api/generated/reviews/reviews'
import type {
  ReviewOut,
  ReviewReplyOut,
} from '../../api/generated/onlineStoreAPI.schemas'
import { useAuth } from '../../hooks/useAuth'
import { StarRating } from './StarRating'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('uk-UA', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  })
}

export function ReviewCard({
  review,
  productId,
}: {
  review: ReviewOut
  productId: number
}) {
  const { user } = useAuth()
  const [showReplies, setShowReplies] = useState(false)
  const [replying, setReplying] = useState(false)

  const adminReplies = review.replies.filter((r) => r.is_admin)
  const userReplies = review.replies.filter((r) => !r.is_admin)

  return (
    <div className="border-b border-gray-100 py-5 last:border-0">
      <div className="flex items-center justify-between">
        <span className="font-medium text-gray-900">{review.author_name}</span>
        <span className="text-xs text-gray-400">{formatDate(review.created_at)}</span>
      </div>
      <div className="mt-1">
        <StarRating value={review.rating} size={16} />
      </div>
      {review.text && (
        <p className="mt-2 whitespace-pre-line text-sm text-gray-700">{review.text}</p>
      )}

      {/* Admin replies — always visible, prominent. */}
      {adminReplies.map((reply) => (
        <AdminReply key={reply.id} reply={reply} />
      ))}

      <div className="mt-3 flex items-center gap-4 text-sm">
        {user && (
          <button
            type="button"
            onClick={() => setReplying((v) => !v)}
            className="font-medium text-gray-600 hover:text-gray-900"
          >
            Відповісти
          </button>
        )}
        {userReplies.length > 0 && (
          <button
            type="button"
            onClick={() => setShowReplies((v) => !v)}
            className="font-medium text-gray-600 hover:text-gray-900"
          >
            {showReplies
              ? 'Сховати відповіді'
              : `Показати відповіді (${userReplies.length})`}
          </button>
        )}
      </div>

      {replying && (
        <ReplyForm
          reviewId={review.id}
          productId={productId}
          onDone={() => setReplying(false)}
        />
      )}

      {/* Normal user replies — collapsed behind the toggle. */}
      {showReplies && (
        <div className="mt-3 space-y-3 border-l-2 border-gray-100 pl-4">
          {userReplies.map((reply) => (
            <div key={reply.id}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-800">
                  {reply.author_name}
                </span>
                <span className="text-xs text-gray-400">
                  {formatDate(reply.created_at)}
                </span>
              </div>
              <p className="text-sm text-gray-600">{reply.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function AdminReply({ reply }: { reply: ReviewReplyOut }) {
  return (
    <div className="mt-3 rounded-md border-l-4 border-red-500 bg-red-50 p-3">
      <div className="flex items-center justify-between">
        <span className="rounded bg-red-600 px-2 py-0.5 text-xs font-semibold text-white">
          Адміністрація Ahet Store
        </span>
        <span className="text-xs text-red-400">{formatDate(reply.created_at)}</span>
      </div>
      <p className="mt-2 text-sm text-red-900">{reply.text}</p>
    </div>
  )
}

function ReplyForm({
  reviewId,
  productId,
  onDone,
}: {
  reviewId: number
  productId: number
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    setBusy(true)
    try {
      await createReply(reviewId, { text })
      queryClient.invalidateQueries({ queryKey: getGetProductReviewsQueryKey(productId) })
      onDone()
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="mt-3">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={2}
        placeholder="Ваша відповідь…"
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
      />
      <div className="mt-1 flex gap-2">
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-gray-900 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-gray-700 disabled:opacity-60"
        >
          {busy ? 'Надсилання…' : 'Надіслати'}
        </button>
        <button
          type="button"
          onClick={onDone}
          className="text-sm text-gray-500 hover:text-gray-900"
        >
          Скасувати
        </button>
      </div>
    </form>
  )
}
