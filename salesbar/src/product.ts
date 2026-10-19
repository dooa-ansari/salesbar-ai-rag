import type { NodeProperty, ProductSummary } from './api'

export type SizeStock = { size: string; stock: number }

export type Product = {
  id: string
  sku: string
  name: string
  description: string
  price: number | null
  currency: string
  category: string
  brand: string
  colours: string[]
  sizes: SizeStock[]
  materials: string[]
  fit: string | null
  season: string | null
  features: string[]
  freeFrom: string[]
}

const SIZE_ORDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL']

function property(properties: NodeProperty[], name: string) {
  return properties.find((item) => item.name === name)?.value
}

function sizeRank(size: string) {
  const index = SIZE_ORDER.indexOf(size)
  if (index !== -1) return index
  const number = Number(size.replace(/\D/g, ''))
  return Number.isNaN(number) ? Number.MAX_SAFE_INTEGER : 100 + number
}

export function toProduct(summary: ProductSummary): Product {
  const named = (key: string) =>
    summary.attributes.filter((attribute) => attribute.key === key).map((attribute) => attribute.name)
  const price = property(summary.properties, 'price')

  return {
    id: summary.id,
    sku: String(property(summary.properties, 'sku') ?? summary.id),
    name: summary.name,
    description: summary.description ?? '',
    price: typeof price === 'number' ? price : null,
    currency: String(property(summary.properties, 'currency') ?? ''),
    category: named('BELONGS_TO')[0] ?? 'Other',
    brand: named('IS_MADE_BY')[0] ?? '',
    colours: named('COMES_IN'),
    sizes: summary.attributes
      .filter((attribute) => attribute.key === 'AVAILABLE_IN')
      .map((attribute) => ({
        size: attribute.name,
        stock: Number(property(attribute.properties, 'stock') ?? 0),
      }))
      .sort((a, b) => sizeRank(a.size) - sizeRank(b.size)),
    materials: named('MADE_OF'),
    fit: named('HAS_FIT')[0] ?? null,
    season: named('SUITED_TO')[0] ?? null,
    features: named('HAS_FEATURE'),
    freeFrom: named('IS_FREE_FROM'),
  }
}

export function inStock(product: Product) {
  return product.sizes.some((size) => size.stock > 0)
}
