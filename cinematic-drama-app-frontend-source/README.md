# Frontend

React 19, TypeScript, Vite, and Tailwind CSS application for browsing dramas, playing episodes, rendering interaction manifests, streaming AI recommendations, and exploring generated branch narratives. The eight routes cover home, detail, player, search, AI search, theater, profile, and branch narrative views.

## Development

```bash
cp .env.example .env
npm ci
npm run dev
```

The local Vite server proxies `/api` to Django at `127.0.0.1:8787`. Run `npm run build` for a production build.

## Mobile

Capacitor 8 is configured for native packaging, and the Android project is included in `android/`. Set `VITE_API_BASE_URL` to an HTTPS backend, then use `npm run android:sync`, `npm run android:open`, or `npm run android:apk`.
