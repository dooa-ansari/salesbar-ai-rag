import { createContext } from 'react'

// "down": the usual bottom-to-top link. "up": a reverse link, top-to-bottom.
export type LinkDirection = 'down' | 'up'

// Tracks which node is waiting to be linked, so a node's "+"/"↑" buttons and
// the canvas' click handler can cooperate.
export type LinkContextValue = {
  linking: { nodeId: string; direction: LinkDirection } | null
  toggleLink: (nodeId: string, direction: LinkDirection) => void
}

export const LinkContext = createContext<LinkContextValue>({
  linking: null,
  toggleLink: () => {},
})
