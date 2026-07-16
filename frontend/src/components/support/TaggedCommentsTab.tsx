import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useCreateReply } from '../../api/generated/reviews/reviews'
import {
  getListTaggedCommentsQueryKey,
  useListTaggedComments,
  useResolveTaggedComment,
} from '../../api/generated/support/support'
import type { TaggedCommentOut } from '../../api/generated/onlineStoreAPI.schemas'

// The "Tagged Comments" queue: product reviews the author flagged as needing a
// support reply. Admins answer (a public ReviewReply) and mark them resolved to
// clear the queue.
export function TaggedCommentsTab() {
  const { data, isLoading } = useListTaggedComments({ query: { refetchInterval: 8000 } })
  const comments = data?.data ?? []

  if (isLoading) return <p className="p-6 text-sm text-gray-400">Завантаження…</p>
  if (comments.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center text-sm text-gray-400">
        Немає позначених коментарів — черга порожня 🎉
      </div>
    )
  }

  return (
    <ul className="flex flex-col gap-4">
      {comments.map((c) => (
        <TaggedComment key={c.id} comment={c} />
      ))}
    </ul>
  )
}

function TaggedComment({ comment }: { comment: TaggedCommentOut }) {
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: getListTaggedCommentsQueryKey() })

  const replyMutation = useCreateReply({ mutation: { onSuccess: invalidate } })
  const resolveMutation = useResolveTaggedComment({ mutation: { onSuccess: invalidate } })

  const sendReply = async () => {
    const trimmed = text.trim()
    if (!trimmed || replyMutation.isPending) return
    setText('')
    try {
      await replyMutation.mutateAsync({ reviewId: comment.id, data: { text: trimmed } })
    } catch {
      setText(trimmed)
    }
  }

  return (
    <li className="rounded-lg border border-amber-200 bg-amber-50/40 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/product/${comment.product_slug}`}
            className="font-medium text-gray-900 hover:underline"
          >
            {comment.product_title}
          </Link>
          <p className="text-xs text-gray-500">
            {comment.author_name} · {'★'.repeat(comment.rating)}
            {'☆'.repeat(5 - comment.rating)}
          </p>
        </div>
        <button
          type="button"
          onClick={() => resolveMutation.mutateAsync({ reviewId: comment.id }).catch(() => {})}
          disabled={resolveMutation.isPending}
          className="shrink-0 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-60"
        >
          Вирішено
        </button>
      </div>

      <p className="mt-2 whitespace-pre-wrap text-sm text-gray-800">{comment.text}</p>

      {comment.replies.length > 0 && (
        <ul className="mt-3 flex flex-col gap-2 border-l-2 border-amber-200 pl-3">
          {comment.replies.map((r) => (
            <li key={r.id} className="text-sm">
              <span className={`font-semibold ${r.is_admin ? 'text-emerald-700' : 'text-gray-700'}`}>
                {r.is_admin ? 'ahetStore' : r.author_name}:
              </span>{' '}
              <span className="text-gray-800">{r.text}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex items-center gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              sendReply()
            }
          }}
          placeholder="Відповісти публічно…"
          className="min-w-0 flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
        />
        <button
          type="button"
          onClick={sendReply}
          disabled={!text.trim() || replyMutation.isPending}
          className="shrink-0 rounded-md bg-gray-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-gray-700 disabled:opacity-60"
        >
          Відповісти
        </button>
      </div>
    </li>
  )
}
