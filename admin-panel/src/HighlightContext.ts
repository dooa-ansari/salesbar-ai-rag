import { createContext } from 'react'

// Broadcasts the current search's traversal to every node/edge, the same way
// LinkContext broadcasts linking state — avoids threading it through props.
export type HighlightContextValue = {
  // Nodes vector search matched directly.
  matchedNodeIds: Set<string>
  // Nodes pulled in only via the live Neo4j traversal from a matched node.
  neighborNodeIds: Set<string>
  highlightedEdgeIds: Set<string>
}

const EMPTY = new Set<string>()

export const HighlightContext = createContext<HighlightContextValue>({
  matchedNodeIds: EMPTY,
  neighborNodeIds: EMPTY,
  highlightedEdgeIds: EMPTY,
})
