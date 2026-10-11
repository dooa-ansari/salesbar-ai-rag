// Split out from Button.tsx so a non-<button> element (e.g. a react-router
// `Link`) can look identical to one.

export type ButtonVariant = 'primary' | 'secondary' | 'outline'
export type ButtonSize = 'sm' | 'md' | 'lg'

const base =
  'inline-flex items-center justify-center rounded-md font-medium transition-colors ' +
  'focus-visible:outline-2 focus-visible:outline-offset-2 ' +
  'disabled:cursor-not-allowed disabled:opacity-50'

const variants: Record<ButtonVariant, string> = {
  primary:
    'bg-primary-600 text-white hover:bg-primary-700 focus-visible:outline-primary-500',
  secondary:
    'bg-secondary-600 text-white hover:bg-secondary-700 focus-visible:outline-secondary-500',
  outline:
    'border border-primary-600 text-primary-700 hover:bg-primary-50 focus-visible:outline-primary-500',
}

const sizes: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
}

export function buttonClassName(
  variant: ButtonVariant = 'primary',
  size: ButtonSize = 'md',
  className = '',
) {
  return `${base} ${variants[variant]} ${sizes[size]} ${className}`
}
