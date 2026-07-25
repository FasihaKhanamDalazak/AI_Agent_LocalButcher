# Chat with Ria — LocalButcher AI Assistant

React + Vite + Tailwind + Framer Motion frontend for LocalButcher's AI
assistant, Ria. Built against the `/api/chat` and `/api/health` contract
in `LOCALBUTCHER_REFERENCE.md`.

## Setup

```bash
npm install
cp .env.example .env   # set VITE_API_URL to your backend
npm run dev
```

## What's here

- **Header** — sticky glass header with the LocalButcher brand mark.
- **StatusBanner** — polls `/api/health` on load and shows a friendly
  "waking up the kitchen" notice while Render's free tier spins up from
  idle (30-50s cold start).
- **Hero** — reproduces the exact fade-up reveal + shimmering gradient
  heading from localbutcher.com's marketing site (`useReveal` hook,
  `.reveal` / `.grad-text` in `styles/index.css`), rebuilt for the chat
  landing with starter chips.
- **ChatInput / ChatContainer / ChatMessage** — the conversation itself.
  Sends `{ message, session_id }` to `POST /api/chat`, renders Ria's
  markdown-ish replies (bullets + line breaks), and renders 0-2 follow-up
  chips per reply — no chip row at all when `follow_ups` is empty
  (that's the deliberate off-topic-redirect behavior, not a bug).
- **useChat** — owns the session_id (one per tab, via
  `crypto.randomUUID()`), message history, and the send/error flow,
  including a distinct, friendlier bubble for 429 rate-limit responses.
- **useHealthCheck** — the polling behind StatusBanner.

## Notes

- Uses `/api/chat`, **not** `/api/chat/stream` — the reference doc flags
  the streaming endpoint as not yet safe to render character-by-character.
- No `sources` UI — the backend no longer returns that field.
- Rate limit is 15 req/min/IP; a 429 renders as a friendly "slow down a
  sec" bubble instead of a raw error.
