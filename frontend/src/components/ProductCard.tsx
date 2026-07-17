import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ProductOut } from '../api/generated/onlineStoreAPI.schemas'
import { useCart } from '../hooks/useCart'
import { useIsStaff } from '../hooks/useIsStaff'
import { formatPrice, reviewsPlural } from '../lib/format'
import { ProductImageCarousel } from './ProductImageCarousel'
import { WishlistButton } from './WishlistButton'

export function ProductCard({
  product,
  noZoom = false,
}: {
  product: ProductOut
  // In horizontal carousels (overflow-clipped), the scale/big-shadow hover gets
  // cut off — use a subtle, non-overflowing hover instead.
  noZoom?: boolean
}) {
  const isStaff = useIsStaff()
  // Prefer the gallery; fall back to the legacy single image for safety.
  const galleryImages =
    product.images && product.images.length > 0
      ? product.images
      : product.image
        ? [product.image]
        : []
  const isUnavailable = !product.is_active || product.stock === 0
  const onSale = product.discount_price != null && product.is_active
  const saving = onSale
    ? Number(product.price) - Number(product.discount_price)
    : 0
  const hoverEffect = noZoom
    ? 'hover:border-gray-300 hover:shadow-md'
    : 'hover:-translate-y-1 hover:border-gray-300 hover:shadow-xl'

  return (
    <div
      className={`group relative z-10 flex h-full flex-col rounded-xl border border-gray-200 bg-white shadow-sm transition-all duration-300 ${hoverEffect} ${
        isUnavailable ? 'opacity-60' : ''
      }`}
    >
      {/* Wishlist heart — overlaid top-right, kept outside the image <Link> so
          it never nests a button inside an anchor. */}
      <WishlistButton
        productId={product.id}
        size="sm"
        className="absolute right-2 top-2 z-20"
      />

      {/* "Новинка" — card-level overlay so it sits above the image slider */}
      {product.is_new && (
        <span className="absolute left-2 top-2 z-20 rounded bg-emerald-500 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-white">
          Новинка
        </span>
      )}

      {/* Image slider (clicking the image opens the product page) */}
      <ProductImageCarousel
        images={galleryImages}
        alt={product.title}
        to={`/product/${product.slug}`}
      />

      <div className="flex flex-1 flex-col gap-2 p-4">
        <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
          {product.category.name}
        </span>
        <Link to={`/product/${product.slug}`}>
          <h2 className="line-clamp-2 text-sm font-semibold text-gray-900 transition hover:text-brand">
            {product.title}
          </h2>
        </Link>

        {/* Rating */}
        {product.reviews_count > 0 && (
          <div className="flex items-center gap-1 text-sm">
            <StarIcon />
            <span className="font-medium text-gray-900">
              {product.average_rating.toFixed(1)}
            </span>
            <span className="text-gray-400">
              ({product.reviews_count} {reviewsPlural(product.reviews_count)})
            </span>
          </div>
        )}

        {/* Stock traffic-light */}
        <StockIndicator
          stock={product.is_active ? product.stock : 0}
        />

        {/* Price block */}
        <div className="mt-auto pt-2">
          {onSale ? (
            <div className="flex flex-col">
              <span className="text-sm text-gray-400 line-through">
                {formatPrice(product.price)}
              </span>
              <span className="text-2xl font-extrabold tracking-tight text-brand">
                {formatPrice(product.discount_price!)}
              </span>
              <span className="mt-0.5 text-xs font-semibold text-green-600">
                Економія: {formatPrice(String(saving))}
              </span>
            </div>
          ) : (
            <span className="text-2xl font-extrabold tracking-tight text-gray-900">
              {formatPrice(product.price)}
            </span>
          )}

          {/* Bonus indicator (loyalty is hidden from staff) */}
          {!isStaff && (
            <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
              <CoinIcon />+{product.bonus_amount} бонусів
            </div>
          )}
        </div>

        {/* Staff can browse but not buy */}
        {!isStaff && <BuyButton productId={product.id} disabled={isUnavailable} />}
      </div>
    </div>
  )
}

function BuyButton({
  productId,
  disabled,
}: {
  productId: number
  disabled: boolean
}) {
  const { addToCart } = useCart()
  const [added, setAdded] = useState(false)
  const [busy, setBusy] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const handleClick = () => {
    setBusy(true)
    addToCart(productId, 1)
      .then(() => {
        setAdded(true)
        if (timerRef.current) clearTimeout(timerRef.current)
        timerRef.current = setTimeout(() => setAdded(false), 2000)
      })
      .finally(() => setBusy(false))
  }

  if (disabled) {
    return (
      <button
        type="button"
        disabled
        className="mt-3 w-full cursor-not-allowed rounded-md bg-gray-200 px-4 py-2 text-sm font-semibold text-gray-500"
      >
        Немає в наявності
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className={`mt-3 w-full rounded-md px-4 py-2 text-sm font-semibold text-white shadow-sm transition disabled:opacity-70 ${
        added ? 'bg-green-600' : 'bg-brand hover:bg-brand-dark'
      }`}
    >
      {added ? 'У кошику! ✓' : 'Купити'}
    </button>
  )
}

function StarIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="#f59e0b" aria-hidden="true">
      <path d="M10 1.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L10 15.9 4.8 17.6l1-5.8L1.5 7.7l5.9-.9z" />
    </svg>
  )
}

function CoinIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" aria-hidden="true">
      <circle cx="10" cy="10" r="8" fill="#fbbf24" stroke="#d97706" strokeWidth="1.5" />
      <circle cx="10" cy="10" r="4.5" fill="none" stroke="#d97706" strokeWidth="1" />
    </svg>
  )
}

const LOW_STOCK_THRESHOLD = 5

// Traffic-light availability: green (in stock) · yellow (running low) · red (out).
function StockIndicator({ stock }: { stock: number }) {
  let color: string
  let label: string
  if (stock <= 0) {
    color = 'bg-red-500'
    label = 'Немає в наявності'
  } else if (stock <= LOW_STOCK_THRESHOLD) {
    color = 'bg-amber-400'
    label = `Закінчується (${stock} шт)`
  } else {
    color = 'bg-green-500'
    label = 'В наявності'
  }
  return (
    <div className="flex items-center gap-1.5 text-xs text-gray-600">
      <span className={`h-2 w-2 shrink-0 rounded-full ${color}`} aria-hidden="true" />
      {label}
    </div>
  )
}
