import type { Product } from '../product'
import type { ChipKind } from './Chip'
import ProductCard from './ProductCard'

export type GridItem = { product: Product; chip?: ChipKind; reasons?: string[] }

function ProductGrid({ items }: { items: GridItem[] }) {
  return (
    <ul className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {items.map(({ product, chip, reasons }) => (
        <ProductCard key={product.id} product={product} chip={chip} reasons={reasons} />
      ))}
    </ul>
  )
}

export default ProductGrid
