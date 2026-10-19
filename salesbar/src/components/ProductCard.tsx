import { swatch } from '../colours'
import { formatPrice } from '../format'
import { inStock, type Product } from '../product'
import Chip, { type ChipKind } from './Chip'
import ProductImage from './ProductImage'

function ProductCard({ product, chip, reasons = [] }: { product: Product; chip?: ChipKind; reasons?: string[] }) {
  const price = formatPrice(product.price, product.currency)
  const available = inStock(product)

  return (
    <li className="group flex flex-col overflow-hidden rounded-xl border-3 border-text bg-background shadow-[6px_6px_0_0_var(--color-text)] transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[8px_8px_0_0_var(--color-brand)]">
      <div className="relative border-b-3 border-text">
        <ProductImage category={product.category} colour={product.colours[0]} />
        {chip && (
          <div className="absolute top-3 left-3">
            <Chip kind={chip} />
          </div>
        )}
        {!available && (
          <div className="absolute top-3 right-3">
            <Chip kind="ruled-out" label="Sold out" />
          </div>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-bold tracking-wider text-brand-green uppercase">{product.brand}</div>
            <h3 className="text-lg leading-tight font-extrabold text-text">{product.name}</h3>
          </div>
          {price && <div className="shrink-0 text-lg font-extrabold text-brand">{price}</div>}
        </div>
        {reasons.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {reasons.map((reason) => (
              <li key={reason} className="rounded bg-chip-near px-1.5 py-0.5 text-xs font-bold text-chip-near-text">
                {reason}
              </li>
            ))}
          </ul>
        )}
        <p className="line-clamp-2 text-sm text-muted">{product.description}</p>
        <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-2">
          {product.colours.map((colour) => (
            <span
              key={colour}
              title={colour}
              className="h-4 w-4 rounded-full border-2 border-text"
              style={{ backgroundColor: swatch(colour) }}
            />
          ))}
          <span className="mx-1 h-4 w-px bg-border" />
          {product.sizes.map(({ size, stock }) => (
            <span
              key={size}
              title={stock > 0 ? `${stock} in stock` : 'Out of stock'}
              className={`rounded border-2 px-1.5 text-xs font-bold ${
                stock > 0 ? 'border-text text-text' : 'border-border text-muted line-through'
              }`}
            >
              {size}
            </span>
          ))}
        </div>
      </div>
    </li>
  )
}

export default ProductCard
