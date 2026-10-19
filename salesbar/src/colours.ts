const SWATCHES: Record<string, string> = {
  beige: '#e8d9b5',
  black: '#3d3545',
  blue: '#2f6fd6',
  brown: '#7a4b2a',
  denim: '#3b5b8c',
  green: '#2f7c13',
  grey: '#9a96a0',
  navy: '#1d2a5b',
  olive: '#6b7a2a',
  orange: '#f28a1e',
  pink: '#fca4bd',
  purple: '#61137d',
  red: '#d42a3c',
  white: '#ffffff',
  yellow: '#f7d83b',
}

export function swatch(colour: string) {
  return SWATCHES[colour.toLowerCase()] ?? '#d6ecc9'
}
