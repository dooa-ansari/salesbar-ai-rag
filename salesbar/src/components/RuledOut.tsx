import type { Product } from '../product'
import Chip from './Chip'

export type RuledOutItem = { product: Product; reasons: string[] }

function RuledOut({ items }: { items: RuledOutItem[] }) {
  if (items.length === 0) return null

  return (
    <details className="rounded-xl border-3 border-text bg-surface p-4">
      <summary className="cursor-pointer font-extrabold text-text">
        Left out for your safety ({items.length})
      </summary>
      <ul className="mt-3 flex flex-col gap-2">
        {items.map(({ product, reasons }) => (
          <li key={product.id} className="flex flex-wrap items-center gap-2 text-sm">
            <Chip kind="ruled-out" />
            <span className="font-bold text-text">{product.name}</span>
            <span className="text-muted">{reasons.join(', ')}</span>
          </li>
        ))}
      </ul>
    </details>
  )
}

export default RuledOut
