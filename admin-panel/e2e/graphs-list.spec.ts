import { expect, test } from '@playwright/test'
import { json, mockApi } from './fixtures'

test('lists saved graphs with their node/edge counts', async ({ page }) => {
  await mockApi(page, {
    'GET /graphs': (route) =>
      json(route, [
        { id: 'g1', name: 'Smith Family Tree', updatedAt: '2026-01-01T00:00:00Z', nodes: 10, edges: 30 },
        { id: 'g2', name: 'Grocery Store Catalog', updatedAt: '2026-01-02T00:00:00Z', nodes: 73, edges: 90 },
      ]),
  })

  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Saved graphs' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Smith Family Tree/ })).toContainText('10 nodes, 30 edges')
  await expect(page.getByRole('link', { name: /Grocery Store Catalog/ })).toContainText('73 nodes, 90 edges')
})

test('shows an empty state with a way to create the first graph', async ({ page }) => {
  await mockApi(page, { 'GET /graphs': (route) => json(route, []) })

  await page.goto('/')

  await expect(page.getByText('No saved graphs yet.')).toBeVisible()
  await page.getByRole('link', { name: 'Create one' }).click()
  await expect(page).toHaveURL(/\/graphs\/new$/)
})

test('shows an error message if the graph list fails to load', async ({ page }) => {
  await mockApi(page, {
    'GET /graphs': (route) => json(route, { detail: 'Database unavailable' }, 500),
  })

  await page.goto('/')

  await expect(page.getByText(/Request failed \(500\)/)).toBeVisible()
})
