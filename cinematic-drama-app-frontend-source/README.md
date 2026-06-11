# Frontend

React 19, TypeScript, Vite, and Tailwind CSS application for browsing dramas, playing episodes, and rendering interaction manifests against the video timeline. The seven routes cover home, detail, player, search, AI search, theater, and profile views.

## Development

```bash
cp .env.example .env
npm ci
npm run dev
```

The local Vite server proxies `/api` to Django at `127.0.0.1:8787`. Run `npm run build` for a production build.

## Mobile

Capacitor 8 is configured for native packaging. Set `VITE_API_BASE_URL` to an HTTPS backend, then run `npm run build`, `npm run cap:sync`, and the appropriate `cap:add:android` or `cap:add:ios` command when creating a native project.
