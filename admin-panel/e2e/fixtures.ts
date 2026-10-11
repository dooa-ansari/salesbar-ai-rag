import type { Page, Route } from '@playwright/test'

export function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

/**
 * Routes every `/api/**` call through a small dispatcher keyed by
 * "METHOD /path" (path with the leading /api stripped), so each test only
 * has to describe the handful of calls it actually makes. An unmocked call
 * fails loudly instead of hitting a real (absent) backend.
 */
export function mockApi(page: Page, handlers: Record<string, (route: Route) => unknown>) {
  return page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const key = `${request.method()} ${url.pathname.replace(/^\/api/, '')}`
    const handler = handlers[key]
    if (!handler) {
      throw new Error(`Unmocked API call in test: ${key}`)
    }
    await handler(route)
  })
}
