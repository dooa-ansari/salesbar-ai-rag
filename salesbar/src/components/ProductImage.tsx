import { swatch } from '../colours'

const SHAPES: Record<string, string[]> = {
  'T-shirts': ['M30 16 L41 10 Q50 19 59 10 L70 16 L88 32 L78 44 L70 38 L70 88 L30 88 L30 38 L22 44 L12 32 Z'],
  Jackets: [
    'M33 12 L43 8 L50 18 L57 8 L67 12 L86 30 L84 80 L74 80 L72 42 L72 90 L28 90 L28 42 L26 80 L16 80 L14 30 Z',
    'M50 18 L50 90',
  ],
  Jeans: ['M28 10 L72 10 L77 90 L56 90 L50 38 L44 90 L23 90 Z', 'M28 19 L72 19'],
  Shoes: ['M10 64 Q12 44 25 44 L40 46 Q52 50 62 58 L84 64 Q93 67 90 76 L10 76 Z', 'M10 76 L90 76 L90 82 L10 82 Z'],
}

const BACKDROPS: Record<string, string> = {
  'T-shirts': 'bg-chip-exact',
  Jackets: 'bg-chip-alternative',
  Jeans: 'bg-chip-near',
  Shoes: 'bg-chip-popular',
}

function ProductImage({ category, colour }: { category: string; colour: string | undefined }) {
  const [outline, ...details] = SHAPES[category] ?? SHAPES['T-shirts']
  const fill = colour ? swatch(colour) : '#ffffff'

  return (
    <div className={`halftone relative flex aspect-square items-center justify-center ${BACKDROPS[category] ?? 'bg-surface'}`}>
      <svg viewBox="0 0 100 100" className="h-3/4 w-3/4 drop-shadow-[4px_4px_0_var(--color-text)]" aria-hidden="true">
        <path d={outline} fill={fill} stroke="var(--color-text)" strokeWidth="3" strokeLinejoin="round" />
        {details.map((path) => (
          <path key={path} d={path} fill={fill} stroke="var(--color-text)" strokeWidth="3" strokeLinejoin="round" />
        ))}
      </svg>
    </div>
  )
}

export default ProductImage
