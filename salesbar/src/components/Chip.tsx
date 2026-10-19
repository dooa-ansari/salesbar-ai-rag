export type ChipKind = 'exact' | 'near' | 'alternative' | 'popular' | 'ruled-out'

const styles: Record<ChipKind, string> = {
  exact: 'bg-chip-exact text-chip-exact-text',
  near: 'bg-chip-near text-chip-near-text',
  alternative: 'bg-chip-alternative text-chip-alternative-text',
  popular: 'bg-chip-popular text-chip-popular-text',
  'ruled-out': 'bg-chip-ruled-out text-chip-ruled-out-text',
}

const labels: Record<ChipKind, string> = {
  exact: 'Exact match',
  near: 'Near match',
  alternative: 'Alternative',
  popular: 'Popular',
  'ruled-out': 'Ruled out',
}

function Chip({ kind, label }: { kind: ChipKind; label?: string }) {
  return (
    <span className={`inline-block rounded-full border-2 border-text px-2.5 py-0.5 text-xs font-extrabold ${styles[kind]}`}>
      {label ?? labels[kind]}
    </span>
  )
}

export default Chip
