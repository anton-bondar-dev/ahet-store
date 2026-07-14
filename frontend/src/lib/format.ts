import type { ProductOut } from '../api/generated/onlineStoreAPI.schemas'

// Formats a decimal string (as returned by the API) into a hryvnia price
// string with two fraction digits. Shared by ProductCard and ProductDetail.
export function formatPrice(value: string): string {
  return `₴${Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

// The price actually charged: the discount price when an active sale applies,
// otherwise the regular price. Returned as a number for arithmetic.
export function effectivePrice(product: ProductOut): number {
  if (product.discount_price != null && product.is_active) {
    return Number(product.discount_price)
  }
  return Number(product.price)
}

// Ukrainian plural for "відгук" (review): 1 відгук, 2 відгуки, 5 відгуків.
export function reviewsPlural(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'відгук'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'відгуки'
  return 'відгуків'
}
