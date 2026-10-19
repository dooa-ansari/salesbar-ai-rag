import { useQuery } from '@tanstack/react-query'
import { listGraphs, listProducts, shopSearch } from './api'
import { toProduct } from './product'

export const CATALOG_NAME = import.meta.env.VITE_CATALOG_NAME ?? 'Clothes Catalog'

export function useCatalog() {
  return useQuery({
    queryKey: ['graphs'],
    queryFn: listGraphs,
    select: (graphs) => graphs.find((graph) => graph.name === CATALOG_NAME) ?? null,
  })
}

export function useProducts(catalogId: string | undefined) {
  return useQuery({
    queryKey: ['products', catalogId],
    queryFn: () => listProducts(catalogId as string),
    select: (products) => products.map(toProduct),
    enabled: Boolean(catalogId),
  })
}

export function useSearch(catalogId: string | undefined, query: string) {
  const trimmed = query.trim()
  return useQuery({
    queryKey: ['search', catalogId, trimmed],
    queryFn: () => shopSearch(catalogId as string, trimmed),
    enabled: Boolean(catalogId) && trimmed !== '',
  })
}
