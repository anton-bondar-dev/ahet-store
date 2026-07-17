import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useToast } from '../hooks/useToast'
import { useWishlist } from '../hooks/useWishlist'

type Size = 'sm' | 'md' | 'lg'

const SIZES: Record<Size, { button: string; icon: string }> = {
  sm: { button: 'h-8 w-8', icon: 'h-4 w-4' },
  md: { button: 'h-9 w-9', icon: 'h-5 w-5' },
  lg: { button: 'h-11 w-11', icon: 'h-6 w-6' },
}

// Heart toggle. Shown to shoppers and anonymous visitors; hidden for staff
// (employees don't shop). Anonymous clicks are intercepted with a toast +
// redirect to login instead of crashing on a 401.
export function WishlistButton({
  productId,
  size = 'md',
  className = '',
}: {
  productId: number
  size?: Size
  className?: string
}) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { showToast } = useToast()
  const { isFavorite, toggle } = useWishlist()

  if (user?.is_staff) return null

  const favorite = isFavorite(productId)
  const dims = SIZES[size]

  const handleClick = (e: React.MouseEvent) => {
    // Product cards wrap the image in a <Link>; never let the heart navigate.
    e.preventDefault()
    e.stopPropagation()
    if (!user) {
      showToast('Будь ласка, увійдіть, щоб додати товар до обраного')
      navigate('/login')
      return
    }
    toggle(productId)
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-pressed={favorite}
      aria-label={favorite ? 'Видалити з обраного' : 'Додати до обраного'}
      title={favorite ? 'В обраному' : 'Додати до обраного'}
      className={`inline-flex items-center justify-center rounded-full bg-white/90 shadow-sm ring-1 ring-gray-200 backdrop-blur transition hover:bg-white hover:ring-gray-300 ${dims.button} ${className}`}
    >
      <svg
        viewBox="0 0 24 24"
        className={`${dims.icon} transition ${
          favorite ? 'text-red-500' : 'text-gray-400'
        }`}
        fill={favorite ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
      </svg>
    </button>
  )
}
