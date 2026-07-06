import type { ProductOut } from '../api/generated/onlineStoreAPI.schemas'
import { productImageUrl } from '../api/http'

function formatPrice(value: string): string {
  return `₴${Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

export function ProductCard({ product }: { product: ProductOut }) {
  const imageUrl = productImageUrl(product.image)
  const isUnavailable = !product.is_active || product.stock === 0
  const onSale = product.discount_price != null && product.is_active

  return (
    <div
      className={`relative flex flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm transition hover:shadow-md ${
        isUnavailable ? 'opacity-60' : ''
      }`}
    >
      {isUnavailable && (
        <span className="absolute left-2 top-2 z-10 rounded bg-red-600 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-white">
          Out of Stock
        </span>
      )}

      <div className="flex aspect-square items-center justify-center bg-gray-50">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={product.title}
            className="h-full w-full object-contain p-3"
            loading="lazy"
          />
        ) : (
          <span className="text-sm text-gray-400">No image</span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
          {product.category.name}
        </span>
        <h2 className="line-clamp-2 text-sm font-semibold text-gray-900">
          {product.title}
        </h2>

        <div className="mt-auto flex items-baseline gap-2 pt-2">
          {onSale ? (
            <>
              <span className="text-lg font-bold text-gray-900">
                {formatPrice(product.discount_price!)}
              </span>
              <span className="text-sm text-gray-400 line-through">
                {formatPrice(product.price)}
              </span>
            </>
          ) : (
            <span className="text-lg font-bold text-gray-900">
              {formatPrice(product.price)}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
