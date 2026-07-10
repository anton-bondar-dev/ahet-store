// Formats a decimal string (as returned by the API) into a hryvnia price
// string with two fraction digits. Shared by ProductCard and ProductDetail.
export function formatPrice(value: string): string {
  return `₴${Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}
