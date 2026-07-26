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
comes back as both text and Deepgram-Aura-synthesized speech, all
over the same socket. There's no frontend for this yet (deliberately —
see "Known placeholders"); it's a backend/agent capability a future UI
will connect to, verified so far with a script that streams synthesized
audio in place of a live microphone.

**Phone-call agent** — real inbound phone calls, via Exotel's
Voicebot/AgentStream applet connecting to `WS /api/v1/calls/stream`. Unlike
every other channel, a caller isn't already authenticated: they can ask
general questions (routed to `search_knowledge_base`) freely, but anything
account-specific first requires stating their registered mobile number,
which `verify_phone_number` checks against `auth_service.get_user_by_phone`
before any other tool is allowed to run. Once verified, every tool call
goes through the *exact same* `app/llm/tool_executor.py` every other
channel uses — same security scoping, same services. Unlike the browser
voice endpoint, this channel doesn't reuse `chat_service`/Gemini directly:
Deepgram's Voice Agent API runs STT (Flux), the LLM ("think", Gemini
2.5 Flash — pinned, since Deepgram's managed Google provider doesn't accept
the `gemini-flash-latest` alias used elsewhere), and TTS (Aura) together
over one WebSocket, and `app/services/telephony_service.py` is purely an
audio/function-call bridge between that and Exotel — see
`app/llm/call_system_prompt.py` and `call_tool_schemas.py` for what the
agent is configured with. English-only (Aura has no Hindi voice, unlike
text chat's multi-language support), and auth on the Exotel side is Basic
Auth on the handshake (Exotel has no HMAC signing like Twilio).

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
- ~~TTS is local/robotic (pyttsx3)~~ — **resolved**: switched to Deepgram
  Aura (same voice as the phone-call agent) once pyttsx3's Windows-only
  SAPI5 dependency turned out to be incompatible with the Linux deploy
  target.
- **One failed voice turn ends the call** — if the chat pipeline errors
  mid-conversation (e.g. an LLM quota hit), the current voice socket
  closes rather than recovering and waiting for the next utterance.
  Acceptable for now; would need explicit handling to change.
- **Phone-call agent has been tested against real Exotel calls** — this
  surfaced two real bugs (audio chunk-size misalignment causing glitching,
  and a sample-rate mismatch causing pitch/speed-distorted audio, since
  this Exotel account's Voicebot Applet UI has no sample-rate selector and
  silently uses 8000 Hz regardless of docs describing an 8k/16k/24k
  choice), both fixed — see backend CLAUDE.md's "Phone-call layer" for
  the details. Also surfaced: this account's Applet has no Basic Auth
  field either, so `EXOTEL_REQUIRE_AUTH=false` exists as an explicit,
  loudly-logged opt-out until that's available.
- **Phone verification is honor-system, not caller-ID-based** — the caller
  states their registered number out loud rather than it being confirmed
  against the network-verified caller ID Exotel provides in the `start`
  event's `from` field. Simpler to build and matches what was asked for,
  but means anyone who knows (or guesses) a registered number can act as
  that customer over the phone. Revisit if this becomes a real product,
  not just a demo.
- **No barge-in/interruption handling in the bridge** — Deepgram's Voice
  Agent protocol has events for it (`UserStartedSpeaking`, etc.) but
  `telephony_service.py` doesn't currently act on them to cut off
  in-progress agent speech early.
- **Pre-verification call turns aren't persisted** — `Conversation`/
  `Message` rows for a call only start once a phone number verifies (needs
  a `user_id` to attach to); the general-Q&A portion before that point
  isn't logged anywhere, unlike text/voice chat's full history.

## Deployment

**Target: Oracle Cloud's Always Free tier, home region Hyderabad
(`ap-hyderabad-1`)** — a persistent Ampere A1 VM (2 OCPU/12GB RAM as of a
June 2026 allocation reduction, still plenty for this app), not a
container platform. Went through two other options first, both ruled out
for concrete reasons worth recording:
- **Koyeb** was the original plan (simpler than a VM) but its free
  web-service tier was discontinued/gated sometime after this project's
  initial research — its dashboard stopped offering a way to create a
  free service at all.
- **Render** has a real free tier, but its nearest region to India is
  Singapore (no Mumbai/India region as of 2026) — ~100-150ms one-way
  network latency, which compounds badly across the phone-call bridge's
  real-time audio relay (Exotel ↔ backend ↔ Deepgram, every leg latency-
  sensitive). A persistent VM has none of Render's 30-60s cold-start risk
  either way, but the region latency was the deciding factor here.

Oracle actually operates real data centers in Hyderabad and Mumbai
(`ap-hyderabad-1`/`ap-mumbai-1`) — picking Hyderabad as the free-tier
home region (a **one-time, permanent choice at account creation**) puts
this backend in the same city Local Butcher operates in, about as close
to zero added network latency as is achievable. Tradeoffs versus a PaaS
free tier: requires a credit/debit card at signup (not charged unless
explicitly upgraded), the free Ampere A1 shape is known to occasionally
hit regional capacity limits when provisioning (may need a retry), and
there's more manual setup (a real VM, not "git push, done").

**`Dockerfile`** at the repo root — multi-layer (deps from `uv.lock`
installed before app code copied in, so code-only changes don't
invalidate the slow dependency-install layer). Build-verified locally for
**both** `linux/amd64` and `linux/arm64` (Oracle's free Ampere shape is
ARM) via `docker buildx build --platform linux/arm64` — every dependency
has aarch64 wheels, nothing broke. This is also exactly where the
pyttsx3-is-Windows-only issue would have surfaced, and didn't, because
`voice_service.py` no longer depends on it (see "Voice layer" in
CLAUDE.md). Migrations are deliberately NOT run automatically on
container start — Supabase already has the schema applied; run
`uv run alembic upgrade head` manually if a migration is genuinely needed
before a deploy.

**`docker-compose.yml` + `Caddyfile`** — Caddy sits in front of the app
container as a reverse proxy, handling TLS automatically (a real
Let's Encrypt cert via a free DDNS hostname — see below — not
self-signed, which matters because Exotel's WSS endpoint explicitly
rejects self-signed certs) and transparently proxying WebSocket upgrades
for both `/api/v1/chat/voice/stream` and `/api/v1/calls/stream` with no
special config needed. The app container itself is never exposed
directly (no `ports:` mapping) — only Caddy is reachable from outside the
VM. **Edit the domain in `Caddyfile` before first run.**

**Steps** (all VM/dashboard/account actions, not code):
1. Create an Oracle Cloud account (oracle.com/cloud/free), home region
   **Hyderabad** — this is permanent, double-check before confirming.
2. Compute → Instances → Create Instance → Ampere A1 Flex shape (Always
   Free eligible), 2 OCPU / 12GB RAM, Ubuntu image, assign a public IP.
   If capacity is unavailable, retry (common with this shape) or fall
   back to `ap-mumbai-1` / a smaller free x86 micro shape.
3. Open ports 80 and 443 in **both** places Oracle requires it: the VCN's
   Security List (or a Network Security Group) AND the instance's own
   `iptables`/`ufw` (Oracle's default images ship with restrictive
   `iptables` rules even after the VCN-level ports are open — a
   well-known first-time gotcha).
4. SSH in, install Docker + the Docker Compose plugin.
5. Get a free hostname pointing at the VM's public IP — e.g.
   [duckdns.org](https://www.duckdns.org) — and put it in `Caddyfile`.
6. Clone this repo, `cd backend`, create `.env` with every variable from
   `.env.example` filled with real production values — **generate a
   fresh `JWT_SECRET_KEY`, don't reuse the dev one** (any tokens issued
   under it become invalid the moment this changes, which is expected
   and fine for a first deploy). `ENVIRONMENT=production`, `DEBUG=false`.
   `CORS_ORIGINS` needs the deployed frontend's exact URL once that
   exists (chicken-and-egg with step 7 below — deploy backend first with
   a placeholder, update once the frontend URL is known, redeploy).
7. `docker compose up -d --build`.
8. Deploy the frontend (see `../frontend/README.md`) to Vercel/Netlify/
   Cloudflare Pages, pointing `VITE_API_URL`/`VITE_WS_URL` at this VM's
   DuckDNS hostname.
9. Update Exotel's Voicebot Applet WSS URL from the ngrok tunnel used for
   local testing to `wss://<your-duckdns-domain>/api/v1/calls/stream` —
   ngrok is no longer needed once this is live, only for local
   dev/testing going forward.

No keep-alive pinger needed here — unlike a PaaS free tier, a persistent
VM never sleeps in the first place.

## Production readiness

Basic hardening (rate limiting, a global exception handler) is in place;
still genuinely missing before treating this as a hardened production
service (separate from "deployed and working," which the above achieves):

- No automated test suite (`pytest` is a listed dependency, unused so far).
- No password reset / refresh-token flow — JWTs just expire after 24h.
- `/health` doesn't check DB connectivity.
- No structured logging / error tracking beyond what prints to the console.
- Rate limiting is in-memory/single-instance — would need a shared
  backend (Redis) to work correctly across multiple processes (a single
  Koyeb free instance is single-process, so this isn't a blocker for the
  current deploy, just a scaling-out limitation).

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
9. **Phone-call agent** — new `WS /api/v1/calls/stream` endpoint for
   Exotel's Voicebot/AgentStream applet, bridging raw call audio to
   Deepgram's Voice Agent API (STT + Gemini 2.5 Flash "think" + Aura TTS
   together, unlike the browser voice endpoint's separate
   STT→chat_service→TTS pipeline). New phone-verification flow
   (`verify_phone_number` → `auth_service.get_user_by_phone`) gates every
   tool except `search_knowledge_base` until a caller states a registered
   number — everything past that point reuses the same
   `app/llm/tool_executor.py` every other channel does. English-only
   (Aura has no Hindi voice). Basic Auth on the handshake, since Exotel
   has no HMAC request signing. See "Known placeholders" for what's still
   untested against a real call.
   