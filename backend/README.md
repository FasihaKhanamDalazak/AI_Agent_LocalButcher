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

**Real-time voice conversation** — the same agent, spoken, with a real
mic button in the app (`ChatInput.jsx`, `useVoiceChat.js`) that both
speaks the reply and shows it as text on screen. `WS
/api/v1/chat/voice/stream` bridges mic audio to Deepgram's Voice Agent
API (STT+Gemini+TTS together, the same product the phone-call agent
uses — see backend CLAUDE.md's "Voice layer") rather than running
STT → chat_service → TTS as three separate steps: real Gemini quota
pressure and response latency on the direct-call path were the reason
for the switch. Every tool is available immediately (the browser
customer is already logged in, unlike a phone caller), and switching
from typing to talking mid-conversation carries the conversation history
over rather than starting fresh. English-only, same underlying reason as
the phone channel (Aura has no Hindi/Telugu voice) — text chat keeps
full multi-language support unaffected.

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
- ~~Orders sat in "pending" forever with no real staff to advance them~~
  — **resolved**: `order_service.auto_progress_orders` (run on a timer by
  `app/services/scheduler.py`) fully automates status progression, since
  this project has no real staff/logistics operation behind it. See
  backend CLAUDE.md's "Order auto-progression" section for the design.
  Set `AUTO_PROGRESS_ORDERS=false` to disable.
- **Support tickets have the same gap, unresolved** —
  `create_support_ticket` files a ticket with `status="open"`, but nothing
  anywhere (chat tool, staff endpoint, or otherwise) ever moves it to
  `in_progress`/`resolved`. Same category of issue as the order-status one
  above, not yet given the same treatment — flagging it here rather than
  fixing it silently, since unlike orders there's no obvious universal
  "resolved after N minutes" rule (a real support issue's actual
  resolution time is genuinely unknowable, unlike a demo order's delivery).
- **No self-serve staff app** — `role = "staff"` is a direct DB edit
  only; two staff API endpoints exist with no UI.
- **No promotions/offers table.**
- **Product catalog is placeholder data**, not the founder's real
  catalog (see "Current data" above).
- ~~No frontend for voice yet~~ — **this was already stale when it was
  written**: a real mic button (`ChatInput.jsx`/`useVoiceChat.js`) exists
  and works. Caught and corrected only when directly asked about it —
  worth remembering this doc can drift from the actual frontend, not just
  the backend.
- ~~TTS is local/robotic (pyttsx3)~~ — **resolved**: switched to Deepgram
  Aura (same voice as the phone-call agent) once pyttsx3's Windows-only
  SAPI5 dependency turned out to be incompatible with the Linux deploy
  target.
- **Browser voice loses live word-by-word captions while speaking** —
  Deepgram's Voice Agent protocol has no interim/partial-transcript event
  (unlike the old raw Listen API this replaced), so the mic button now
  just shows "Listening…" until the full transcript arrives at once,
  instead of captions appearing as the customer talks.
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

**Target: Render's free tier.** Went through two other options first,
both ruled out for concrete reasons worth recording:
- **Koyeb** was the original plan (simplest option) but its free
  web-service tier was discontinued/gated sometime after this project's
  initial research — its dashboard stopped offering a way to create a
  free service at all.
- **Oracle Cloud's Always Free VM** (a persistent, never-sleeps ARM
  instance, with real data centers in Hyderabad/Mumbai — as close to zero
  added network latency as achievable for this app's Exotel-in-India
  traffic) was the next choice, technically the best fit. Ruled out
  because it requires a credit/debit card at signup — a hard constraint,
  not a preference, so this wasn't negotiable.

Landed on Render knowingly accepting its real tradeoff: no card required,
but its nearest region to India is Singapore (no Mumbai/India region as
of 2026) — roughly 100-150ms one-way network latency, which compounds
across the phone-call bridge's real-time audio relay (Exotel ↔ backend ↔
Deepgram, every leg latency-sensitive). Noticeably worse call experience
than a same-region VM would give, accepted as the cost of not needing a
card. Its free web service also sleeps after 15 min idle with a 30-60s
cold start — mitigated with an external keep-alive pinger (step 4 below),
which keeps it from ever actually going idle long enough to sleep in
normal operation, though this remains one more moving part than a
persistent VM has (if the pinger itself has downtime, the next inbound
call during that window can still miss Exotel's ~10s response budget).

**`Dockerfile`** at the repo root — multi-layer (deps from `uv.lock`
installed before app code copied in, so code-only changes don't
invalidate the slow dependency-install layer). Build-verified locally
(`docker build .` succeeds cleanly on this Linux base image) — this is
exactly where the pyttsx3-is-Windows-only issue would have surfaced, and
didn't, because `voice_service.py` no longer depends on it (see "Voice
layer" in CLAUDE.md). Migrations are deliberately NOT run automatically
on container start — Supabase already has the schema applied; run
`uv run alembic upgrade head` manually if a migration is genuinely needed
before a deploy.

**Steps** (all dashboard/account actions, not code):
1. Push this repo to GitHub (Render deploys from a connected repo).
2. Create a Render account (no card required for the free web-service
   path) → New → Web Service → connect this repo → set the root
   directory to `backend` (monorepo — the `Dockerfile` lives there, not
   at the repo root) → Dockerfile-based build → free instance type.
3. Set every env var from `.env.example` in Render's dashboard with real
   production values — **generate a fresh `JWT_SECRET_KEY`, don't reuse
   the dev one** (any tokens issued under it become invalid the moment
   this changes, which is expected and fine for a first deploy).
   `ENVIRONMENT=production`, `DEBUG=false`. `CORS_ORIGINS` needs the
   deployed frontend's exact URL once that exists (chicken-and-egg with
   step 5 below — deploy backend first with a placeholder, update once
   the frontend URL is known, redeploy).
4. Set up a free external pinger (e.g. cron-job.org, UptimeRobot) hitting
   `https://<your-app>.onrender.com/health` every ~10-14 minutes (under
   Render's 15-min sleep threshold), so the instance never actually goes
   idle long enough to sleep.
5. Deploy the frontend (see `../frontend/README.md`) to Vercel/Netlify/
   Cloudflare Pages, pointing `VITE_API_URL`/`VITE_WS_URL` at this
   backend's Render URL.
6. Update Exotel's Voicebot Applet WSS URL from the ngrok tunnel used for
   local testing to `wss://<your-app>.onrender.com/api/v1/calls/stream` —
   this also means ngrok is no longer needed once this is live, only for
   local dev/testing going forward.

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
- ~~Gemini's free tier has both a per-minute AND a 20-request/day cap —
  budget live chat testing accordingly~~ — **less urgent now**: text chat
  moved to Deepgram's managed Gemini integration (see CLAUDE.md's "LLM
  layer") specifically to get off that 20/day cap, same as voice/calls
  already had. Still applies if testing the original direct-Gemini path
  (`gemini_client.py`), kept intact as an unused rollback option.

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
10. **Browser voice switched to the phone-call agent's architecture** —
    `WS /api/v1/chat/voice/stream` now bridges to Deepgram's Voice Agent
    API too, replacing the separate STT→chat_service→TTS pipeline entry
    #8 above describes (that pipeline is gone, not just deprioritized;
    entry #8 is left as historical record of what was true when written).
    Real Gemini quota pressure and response latency on the direct-call
    path were the reasons. Unlike phone calls, the browser customer is
    already authenticated, so there's no verification gate — every tool
    is available immediately, and prior conversation history is preloaded
    when continuing a conversation started via text chat. Found and fixed
    two real bugs only visible by testing against the live Deepgram
    service: multi-fragment assistant replies were overwriting instead of
    accumulating (dropping text that was still audibly spoken), and the
    static greeting was getting duplicated (Deepgram fires a real
    `ConversationText` event for it too, contrary to what was assumed).
    Also corrected a stale doc claim in the process — a real mic button
    already existed in the frontend before this change; "no frontend for
    voice" was already wrong when written.
11. **Text chat migrated to Deepgram too — all three channels now avoid
    `GEMINI_API_KEY`'s free-tier quota (20 requests/day)**, not just
    voice/calls. `app/llm/deepgram_chat_client.py` drives Gemini via
    Deepgram's Voice Agent `InjectUserMessage` (text straight to the
    "think" step, no real speech needed) rather than the direct
    google-genai SDK call `gemini_client.py` made — that original path is
    kept intact, unused, as a deliberate rollback option. Found a new,
    undocumented Deepgram behavior in testing: even on this text-only
    path, a reply requiring a tool-call round trip needs *some* audio
    streamed periodically or it hits `CLIENT_MESSAGE_TIMEOUT` before
    finishing — a background silent-audio sender fixes it. Also required
    extracting a shared `deepgram_client.get_client()` to avoid a genuine
    circular import (`chat_service → deepgram_chat_client → voice_service
    → chat_service`). Verified end-to-end: simple replies, tool-calling
    replies, multi-turn context (confirmed history preload works),
    follow-up chip parsing, and Hindi/Hinglish (which still works here,
    unlike the voice channels — nothing in this path touches audio the
    customer hears, so Aura's Hindi/Telugu TTS gap doesn't apply).
    Model is pinned to `gemini-2.5-flash` for this path (Deepgram rejects
    the `gemini-flash-latest` alias) — a real, accepted tradeoff versus
    the original path's auto-updating alias.
   