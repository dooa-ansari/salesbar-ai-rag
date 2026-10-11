import { expect, test } from '@playwright/test'
import { json, mockApi } from './fixtures'

test('searching highlights the matched node and shows the synthesized answer', async ({ page }) => {
  await mockApi(page, {
    'GET /graphs/g1': (route) =>
      json(route, {
        id: 'g1',
        name: 'Smith Family Tree',
        text: null,
        nodes: [
          {
            id: 'robert',
            type: 'graph',
            position: { x: 0, y: 0 },
            data: { name: 'Robert Smith', type: 'Person', properties: [] },
          },
          {
            id: 'james',
            type: 'graph',
            position: { x: 400, y: 0 },
            data: { name: 'James Smith', type: 'Person', properties: [] },
          },
        ],
        edges: [{ id: 'e1', source: 'robert', target: 'james', relationship: 'Father' }],
      }),
    'POST /graphs/g1/search': (route) =>
      json(route, {
        query: 'who is the father of james?',
        answer: 'Robert Smith is the father of James Smith.',
        results: [
          {
            id: 'robert',
            name: 'Robert Smith',
            type: 'Person',
            description: null,
            properties: [],
            score: 0.93,
            relationships: [
              { relationship: 'Father', direction: 'outgoing', otherId: 'james', otherName: 'James Smith' },
            ],
          },
        ],
      }),
  })

  await page.goto('/graphs/g1')
  await page.getByRole('button', { name: 'Search' }).click()

  const queryInput = page.getByLabel('Search query')
  await queryInput.fill('who is the father of james?')
  await page.getByRole('button', { name: 'Send' }).click()

  await expect(page.getByText('Robert Smith is the father of James Smith.')).toBeVisible()
  await expect(page.getByText('93% match')).toBeVisible()
  await expect(page.getByText('→ Father → James Smith')).toBeVisible()

  // The matched node (robert) gets the "matched" ring; its neighbor (james,
  // pulled in only via the live traversal) gets the "neighbor" ring.
  await expect(page.locator('[data-id="robert"] .relative.w-64')).toHaveClass(/ring-primary-300/)
  await expect(page.locator('[data-id="james"] .relative.w-64')).toHaveClass(/ring-secondary-300/)
})

test('a search with no matches says so instead of showing empty results', async ({ page }) => {
  await mockApi(page, {
    'GET /graphs/g1': (route) =>
      json(route, { id: 'g1', name: 'Empty-ish', text: null, nodes: [], edges: [] }),
    'POST /graphs/g1/search': (route) =>
      json(route, { query: 'anything', answer: null, results: [] }),
  })

  await page.goto('/graphs/g1')
  await page.getByRole('button', { name: 'Search' }).click()
  await page.getByLabel('Search query').fill('anything')
  await page.getByRole('button', { name: 'Send' }).click()

  await expect(page.getByText('No matching nodes found.')).toBeVisible()
})
