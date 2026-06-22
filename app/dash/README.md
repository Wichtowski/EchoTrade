# EchoDash

EchoTrade dashboard built with [Vike](https://vike.dev/) + React + Tailwind CSS.
The dashboard now pre-renders static HTML and is intended to deploy to Cloudflare Pages, while the API stays on the Contabo VPS.

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

The static Pages artifact is written to `app/dash/dist/client`.

If Wrangler complains about `.wrangler/deploy/config.json` or a missing redirected `wrangler.json`,
remove the local `.wrangler/` directory. That state comes from an older Workers-style deploy flow and
is not needed for Cloudflare Pages.

Environment files are resolved from `app/dash`:

- `.env.development` -> local dev API base
- `.env.production` -> Cloudflare Pages production API base

## Deploy to Cloudflare Pages

The repository includes `.github/workflows/deploy-dash.yml`, which:

- builds `app/dash`
- deploys `dist/client` to Cloudflare Pages
- expects `VITE_API_BASE_URL` to point at `https://api.oskarwichtowski.com`

## Features (Phase 1+)

- Position management (add/edit/delete)
- Portfolio overview with P/L
- Allocation chart
- Concentration warnings
- Market data display
