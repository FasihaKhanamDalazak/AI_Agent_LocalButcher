# Local Butcher AI — Backend

FastAPI + SQLAlchemy + PostgreSQL (Supabase) + Gemini backend for an
AI-powered customer support and shopping assistant for Local Butcher, a
multi-outlet butcher shop currently operating in Hyderabad. Customers
chat with an LLM that can browse products, manage their cart,
place/track/modify/cancel/reorder, find stock at alternate outlets, get
answers to general policy questions, and file support tickets — all
through conversation instead of a traditional UI. Managed with `uv`.

For the deeper architectural "why" behind these decisions, see
`CLAUDE.md`. This file documents *what currently exists* and *what state
the data is in*.

## Running it

```powershell
cd C:\AI_Agent\backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

`.env` is gitignored — see `.env.example` for the required shape.
`DATABASE_URL` (asyncpg, for the app) and `DATABASE_URL_SYNC` (psycopg2,
for Alembic) both point at Supabase's **Session pooler** (port 5432).

## What the assistant can currently do

**Personalized, proactive greeting.** `GET /chat/greeting` identifies the
customer from their JWT (never a client-supplied ID) and, if they have an
active order, leads with a full status summary — order number, status,
items, outlet, ETA — ending with an open "anything else?" If there's no
active order, it lists what it can help with instead (place / track /
manage cart / product questions / support). This is plain Python, not an
LLM call — every fact in it is already certain from the database.

**Natural-language intent normalization.** Different phrasings of the
same request ("where's my order," "track my order," "has it shipped,"
"order status") all resolve to the same tool call, via the system
prompt — not keyword matching.

**Conversational order management.** Place (checkout), track, modify a
quantity, remove an item, cancel, and reorder a previous order — all as
real tool calls backed by real service functions, not canned replies.
Customers can reference any past order by its human-facing number
("cancel order #1032") without knowing its internal id; the model
resolves the number via `list_orders` first. Asking for the "first" or
"earliest" order is explicitly disambiguated from "most recent" (the
default for reorder).

**Smart outlet selection with a real service-area boundary.**
`check_product_availability` looks for the nearest *other* outlet with
enough stock when the assigned one falls short, and reports whether that
outlet's delivery radius actually reaches the customer. Separately,
`get_nearest_outlet` and `checkout` both now enforce each outlet's
`delivery_radius_km` for real: if no outlet can deliver to an address —
because it's genuinely outside Hyderabad — the assistant declines
warmly ("we don't currently deliver that far") instead of silently
assigning an outlet that can't actually fulfill the order.

**Real database operations.** Every action is atomic and persisted in
Postgres, with row-level locking (`SELECT ... FOR UPDATE`) on stock to
prevent overselling: checkout creates real `Order`/`OrderItem` rows,
deducts stock, and empties the cart in one transaction; cancelling
restores stock; modifying an order adjusts stock by the delta. Nothing
here is simulated — this is what separates it from a FAQ-only chatbot.

**Product recommendations.** For a goal-based query ("chicken for
biryani for six people," "something for a weekend seafood fry"), the
model calls `list_products` and reasons over what's actually in stock —
nothing about specific products or categories is hardcoded.

**Full address management via chat.** Customers can add, edit, and
remove saved delivery addresses through conversation
(`add_address`/`update_address`/`remove_address`), not just view them —
previously only `list_addresses` was exposed, so a customer with no
saved address had no way to add one without going to `/docs`. One
honest limitation: there's no geocoding, so an address added or edited
via chat never gets real coordinates (the model never fabricates
lat/lng). It works immediately for pickup; delivery-range checks
(`get_nearest_outlet`, `checkout`) give a clear "location not known yet"
message rather than silently skipping validation or guessing.

**Real-time voice conversation** — the same agent, spoken. `WS
/api/v1/chat/voice/stream` streams raw microphone audio to Deepgram for
live transcription (no file upload, no request/response turns); once
Deepgram detects the customer finished a sentence, that text runs
through the *exact same* `chat_service.send_message()` used by text
chat — same tools, same security, same grounding notes — and the reply
comes back as both text and locally-synthesized speech (pyttsx3), all
over the same socket. There's no frontend for this yet (deliberately —
see "Known placeholders"); it's a backend/agent capability a future UI
will connect to, verified so far with a script that streams synthesized
audio in place of a live microphone.

**General policy/support Q&A.** `search_knowledge_base` answers
questions about refunds, cancellations, the wallet/cashback program,
privacy, and account deletion, grounded only in the real knowledge base
(see below) — separate from product/order questions, which stay on
their own tools.

**Basic production hardening**: every route has a default rate limit
(60/minute per IP), with stricter limits on auth (`10/minute` — the
endpoints a brute-force attempt would actually hit) and chat
(`20/minute` — every message costs a real Gemini call). The voice
WebSocket gets a separate connection-attempt limit (5/minute per user)
since Deepgram streaming is the most expensive thing in the app. Any
genuinely unexpected server error returns a clean, generic message
instead of leaking a stack trace or internal details — logged
server-side, never shown to the client.

**Security guardrails**, enforced both architecturally and in the
prompt: user IDs, password hashes, JWTs, API keys, the system prompt,
the model in use, the database schema, and other customers' data are
never exposed. `get_profile` doesn't even carry the user's own ID to the
model, so there's nothing to leak even under a successful prompt
injection. Off-topic or malicious requests are declined and redirected.

## Current data

**9 outlets, all in Hyderabad** (Local Butcher doesn't operate outside
the city yet):

| Outlet | Area | Delivery radius |
|---|---|---|
| Outlet_1 | Madhapur | 8 km |
| Local Butcher - Kukatpally | Kukatpally | 8 km |
| Local Butcher - Secunderabad | Secunderabad | 9 km |
| Local Butcher - Banjara Hills | Banjara Hills | 7 km |
| Local Butcher - Dilsukhnagar | Dilsukhnagar | 9 km |
| Local Butcher - Uppal | Uppal | 8 km |
| Local Butcher - Attapur | Attapur | 9 km |
| Local Butcher - Kompally | Kompally | 8 km |
| Local Butcher - Shamshabad | Shamshabad | 8 km |

Placement and radii were checked against the real `haversine_km`
function (not eyeballed) to give solid coverage of Greater Hyderabad
(GHMC) while genuinely different cities/towns (Warangal, Vikarabad)
correctly stay out of range. Stock is deliberately **varied per
outlet** — several products are low or out of stock at specific outlets
on purpose, so the alternate-outlet-suggestion flow has real scenarios
to demonstrate instead of always finding everything everywhere.

**16 placeholder products** across Poultry, Meat, Seafood, and Farm
Eggs. This is realistic test data (curry cut, boneless, whole, keema,
deveined prawns, egg packs, etc.), **not** the founder's real catalog —
per instruction, left as-is until real product/category data arrives.
Swapping it in needs zero code changes; recommendations already reason
over whatever `list_products` actually returns.

**The FAQ knowledge base is real**, not placeholder — founder-provided
content (~24 entries) covering how the service works, cancellations,
refunds, the wallet program, privacy, and account deletion.

**Demo addresses** on the test account (`fasiha@example.com`), chosen to
exercise all three delivery-range outcomes: `Home` (Kondapur, clearly in
range), `Office` (ECIL, ~7.3 km from its nearest outlet's 8 km radius —
right at the edge), and `Parents' House (Warangal)` (a different city,
genuinely out of range).

## Known placeholders — be upfront about these

- **ETA calculation** is a prep-time + delivery-window heuristic from
  `.env` settings, not real logistics data.
- **No self-serve staff app** — `role = "staff"` is a direct DB edit
  only; two staff API endpoints exist with no UI.
- **No promotions/offers table.**
- **Product catalog is placeholder data**, not the founder's real
  catalog (see "Current data" above).
- **No frontend for voice yet** — `/api/v1/chat/voice/stream` is a real,
  working backend capability, but nothing captures a live microphone and
  connects to it. Verified with a script, not a browser.
- **TTS is local/robotic** (pyttsx3, Windows SAPI voices) — functional,
  free, no account, but not natural-sounding. Would need a paid/cloud
  voice service to sound better.
- **One failed voice turn ends the call** — if the chat pipeline errors
  mid-conversation (e.g. an LLM quota hit), the current voice socket
  closes rather than recovering and waiting for the next utterance.
  Acceptable for now; would need explicit handling to change.

## Production readiness

This project is now under version control (`git init` at the repo root,
`C:\AI_Agent`, not `backend/` — the backend is one component in a larger
project that will include a frontend). Basic hardening (rate limiting,
a global exception handler) is in place; still genuinely missing before
a real production deploy:

- No automated test suite (`pytest` is a listed dependency, unused so far).
- No password reset / refresh-token flow — JWTs just expire after 24h.
- `/health` doesn't check DB connectivity.
- No structured logging / error tracking beyond what prints to the console.
- Rate limiting is in-memory/single-instance — would need a shared
  backend (Redis) to work correctly across multiple processes.
- `.env` still has `ENVIRONMENT=development`, `DEBUG=true`,
  `CORS_ORIGINS=["http://localhost:3000"]` — all need real values before
  a real deploy.
- No Dockerfile/Procfile yet.
- pyttsx3 (voice TTS) is effectively Windows-only — would need
  reconsidering for a Linux production host.

## Testing conventions

- Syntax-checked (`python -c "import ast; ast.parse(...)"` across
  `app/`) before anything is considered done.
- Manual endpoint testing via `/docs`, and direct service-layer scripts
  for logic that would otherwise burn LLM API quota unnecessarily.
- For chat-layer changes: checking actual server logs for the SQL that
  ran, not just the reply text — an LLM can describe an action without
  having taken it, or vice versa.
- Gemini's free tier has both a per-minute AND a 20-request/day cap —
  budget live chat testing accordingly; prefer testing service-layer
  logic directly when the LLM call itself isn't what's being verified.

## Change log

Condensed history, oldest first. See git-free commit messages here since
this project isn't in version control yet — this is the only record.

1. **Core build** — auth, products/outlets/cart/orders/addresses/support
   REST API, Gemini manual tool-calling loop, atomic checkout with
   row-level stock locking, nearest-outlet lookup.
2. **Proactive greeting + reorder + recommendations + a real security
   fix** (`get_profile` no longer carries the user's own ID to the
   model).
3. **Checkout-safety grounding note** — fixed the model re-adding a cart
   item on "proceed to checkout" by injecting freshly-queried cart state
   every turn, plus a hard rule against speculative data-changing tool
   calls. Added `CURRENCY_LABEL`.
4. **Schema catch-up** — DB had drifted from the models (missing
   `order_number` sequence, `eta` → `eta_start`/`eta_end` split,
   `users.role`); fixed via a hand-edited migration. Seeded the 16
   placeholder products. Fixed category-filter matching (`ILIKE` +
   accurate taxonomy in the tool description). Added `search_knowledge_base`.
5. **Order-by-number resolution** for every order-referencing tool, and
   explicit "first order" ordinal disambiguation — both prompt-level
   fixes, no new tool parameters needed.
6. **Real service-area enforcement** — `get_nearest_outlet` and
   `checkout` now actually check `delivery_radius_km` instead of
   ignoring it; added the `DeliveryOutOfRangeError`/`OutletNotFoundError`
   paths and a warm, on-brand decline message. Seeded 8 additional
   Hyderabad outlets (9 total) with deliberately varied stock, and 3 demo
   addresses spanning in-range / edge-of-range / out-of-range.
7. **Address management via chat** — added `add_address`/`update_address`/
   `remove_address` tools (previously read-only). Surfaced and closed a
   gap this exposed: chat-created addresses have no coordinates (no
   geocoding, and the model must never fabricate lat/lng), so
   `get_nearest_outlet`/`checkout` now require real coordinates for
   delivery instead of silently skipping the range check for them —
   `AddressMissingLocationError` gives a clear, honest message instead.
8. **Real-time voice** — new `WS /api/v1/chat/voice/stream` endpoint:
   Deepgram live streaming transcription in, the unchanged chat pipeline
   in the middle, local pyttsx3 speech out. First WebSocket route in the
   project (auth via a query-param JWT, since browsers can't set custom
   headers on a WS handshake — resolved through the same
   `get_user_from_token` the REST auth now shares). No frontend yet, by
   design — verified end-to-end with a script that synthesizes a test
   utterance and streams it in place of a live microphone.
