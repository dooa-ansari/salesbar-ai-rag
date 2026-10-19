export function formatPrice(price: number | null, currency: string): string | null {
  if (price === null) return null
  if (/^[A-Za-z]{3}$/.test(currency)) {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(price)
  }
  return String(price)
}
