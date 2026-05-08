# DeepSecure Frontend

Next.js application for the DeepSecure dashboard and interactive demo.

## Development

```bash
# Install dependencies
npm install

# Start development server (http://localhost:3000)
npm run dev

# Type check
npm run type-check

# Lint
npm run lint

# Build for production
npm run build

# Start production server
npm run start
```

## Architecture

- **Framework:** Next.js (App Router)
- **Auth Pattern:** BFF — httpOnly cookies, CSRF tokens, server-side JWT management
- **CSS:** Tailwind CSS
- **State:** TanStack Query (server) + Zustand (client) — coming in Phase 2

## Route Groups

| Group | Purpose | Auth |
|-------|---------|------|
| `(auth)` | Login, SSO callbacks | Public |
| `(dashboard)` | Authenticated pages | Required |
| `(public)` | Demo, landing | Public |
| `api/auth` | BFF auth routes | Public |
| `api/proxy` | BFF proxy to backend | Required |

## Environment

See `.env`, `.env.development`, `.env.production` for configuration.
Generate local secrets: `scripts/generate-env.sh` (created by WS-A5).
