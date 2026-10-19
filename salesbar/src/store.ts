import { create } from 'zustand'

export type SortOrder = 'featured' | 'price_asc' | 'price_desc'

type ShopState = {
  query: string
  category: string | null
  sort: SortOrder
  setQuery: (query: string) => void
  setCategory: (category: string | null) => void
  setSort: (sort: SortOrder) => void
}

export const useShopStore = create<ShopState>((set) => ({
  query: '',
  category: null,
  sort: 'featured',
  setQuery: (query) => set({ query }),
  setCategory: (category) => set({ category }),
  setSort: (sort) => set({ sort }),
}))
