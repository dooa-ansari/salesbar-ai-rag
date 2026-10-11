import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
// vitest/config re-exports Vite's defineConfig, extended to also type-check
// the `test` option below.
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Mirrors nginx.conf's /api/ -> backend proxy, so the app can always call
    // a same-origin /api/* path (avoids CORS) whether run via `vite dev` or
    // through the built, containerized frontend. The target is overridden by
    // docker-compose.override.yml to the backend's service name, since
    // "localhost" inside that container means the frontend container itself.
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    // Vitest's default include pattern also matches *.spec.ts — which is
    // what the Playwright suite under e2e/ uses, and Playwright's own
    // test()/expect() don't run under Vitest.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
