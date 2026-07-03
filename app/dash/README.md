# EchoDash

EchoTrade dashboard built with [Vike](https://vike.dev/) + React + Tailwind CSS.
The dashboard renders with Vike SSR on Cloudflare Workers, while the API stays on the Contabo VPS.

## Setup

```bash
cd app/dash
bun install
bun run dev
```

## Build

```bash
cd app/dash
bun run build
```

The build writes browser assets to `app/dash/dist/client` and the Worker SSR bundle to `app/dash/dist/server`.

Environment files are resolved from `app/dash`:

- `.env.development` -> local dev API base
- `.env.production` -> Cloudflare Workers production API base

## Deploy to Cloudflare Workers

The repository includes `.github/workflows/release-deploy.yml`, which:

- builds `app/dash`
- deploys the generated Worker bundle using `app/dash/dist/server/wrangler.json`
- injects `VITE_API_BASE_URL=https://apiechotrade.oskarwichtowski.com`
- injects `VITE_APP_VERSION` from the release tag

## Features (Phase 1+)

- Position management (add/edit/delete)
- Portfolio overview with P/L
- Allocation chart
- Concentration warnings
- Market data display
