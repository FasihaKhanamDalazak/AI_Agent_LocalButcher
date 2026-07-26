# Local Butcher AI — Frontend

React + Vite + Tailwind frontend for the Local Butcher AI assistant —
consumes the backend's REST API (`../backend`) plus its two WebSocket
endpoints (browser voice chat, and indirectly the phone-call agent, which
this frontend never talks to directly — that's Exotel's job).

## Setup

```bash
npm install
cp .env.example .env   # set VITE_API_URL / VITE_WS_URL to your backend
npm run dev
```

## Environment variables

Both are read at **build time** (Vite bakes them into the static bundle —
setting them only in a runtime `.env` on a deployed static host does
nothing; they must be set as build-time env vars in whatever platform
builds the site):

- `VITE_API_URL` — backend base URL, no trailing slash (e.g.
  `http://localhost:8000` locally, `https://<app>.koyeb.app` deployed).
- `VITE_WS_URL` — WebSocket base, no trailing slash, matching scheme
  (`ws://` locally, `wss://` once the backend is served over HTTPS).

## What's here

- **AuthPage** — login/register, JWT stored via `utils/authStorage.js`.
  `useAuthState`/`AuthContext` own the token + current-user state and a
  global 401 handler that logs the session out from anywhere a request
  comes back unauthorized.
- **ChatPage** — the main experience: `ChatContainer`/`ChatMessage`/
  `ChatInput` for text chat (`useChat`, one conversation per session),
  plus slide-over panels for **Cart**, **Orders**, **Addresses**, and
  **Account** (`CartPanel`, `OrdersPanel`, `AddressesPanel`,
  `AccountPanel`) — each fetches fresh from the backend every time it's
  opened, not just once, so anything changed elsewhere (including by the
  phone-call agent — see backend README) shows up on next open/reload.
  `FollowUpChips` renders the 0-2 suggested replies the backend attaches
  to each turn.
- **useVoiceChat** — real-time browser voice, streams raw mic audio
  (resampled client-side to 16kHz linear16 PCM, matching
  `voice_service.open_transcription_stream` on the backend exactly) over
  `WS /api/v1/chat/voice/stream`, plays back the spoken reply.
- **StaffDashboardPage** — reachable at the bare path `/staff` (no
  react-router — see `App.jsx`'s comment for why that's a deliberate,
  single-page exception). Real enforcement is the backend's
  `get_current_staff_user` 403; this page's own role check is UX only.
- **services/api.js** — every REST call the app makes, one function per
  backend endpoint (auth, cart, orders, addresses, outlets, products,
  support tickets, staff). `services/httpClient.js` is the shared axios
  instance (base URL, auth header injection, the global 401 hook above).

## Deployment

Static SPA build (`npm run build` → `dist/`) — deploy to any static host.
Two things already prepared for the free options most likely to be used:

- **`vercel.json`** — SPA fallback rewrite (`/*` → `/index.html`), needed
  because `/staff` (see above) isn't a real route the static host would
  otherwise know to serve `index.html` for on direct navigation/refresh.
- **`public/_redirects`** — same fallback, Netlify/Cloudflare Pages syntax.

Whichever platform is used, set `VITE_API_URL`/`VITE_WS_URL` as **build-time**
environment variables in its dashboard before triggering a build — not
just in a local `.env` (that file never leaves your machine). Build
command: `npm run build`; output directory: `dist`.

## Known gaps

- No automated tests.
- One large JS chunk (~180kB gzipped) — Vite warns about this on build;
  code-splitting would help but wasn't worth the complexity for a project
  this size yet.
- No error boundary — an unhandled render error blanks the page instead
  of showing a fallback UI.
