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
