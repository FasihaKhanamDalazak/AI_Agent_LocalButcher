# Local Butcher AI — Backend

Context file for Claude Code. Read this before making changes — it captures
decisions made over an extended design + build process that aren't always
obvious from the code alone.

## What this is

An AI-powered customer support and shopping assistant backend for a
multi-outlet butcher shop ("Local Butcher"). Customers chat with an LLM
that can look up products, manage their cart, place/track/modify/cancel
orders, find stock at alternate outlets, and file support tickets — all
through natural conversation instead of a traditional UI. Built as an
internship project; the founder will eventually test it directly.

## Tech stack

- **Backend**: FastAPI, Python 3.12, managed with `uv` (not pip/poetry)
- **DB**: PostgreSQL via Supabase, **Session pooler** connection (not
  Direct, not Transaction pooler — see "Database" below for why)
- **ORM**: SQLAlchemy 2.0 async (asyncpg driver for the app, psycopg2 for
  Alembic migrations)
- **Auth**: JWT (python-jose), bcrypt password hashing (passlib)
- **LLM**: Google Gemini via `google-genai` SDK, manual tool-calling loop
  (not the SDK's automatic function calling — see "LLM layer" below)
- **Migrations**: Alembic

## Running it

```powershell
cd C:\AI_Agent\backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

`.env` is gitignored and holds real secrets — never commit it. See
`.env.example` for the required shape. Two DB URLs are needed:
`DATABASE_URL` (asyncpg, for the app) and `DATABASE_URL_SYNC` (psycopg2,
for Alembic only).

## Project layout

```
app/
├── main.py              FastAPI app factory, /health
├── core/
│   ├── config.py          ALL settings — env-var driven, nothing hardcoded
│   └── security.py        password hashing, JWT creation
├── db/
│   ├── base_class.py       shared declarative Base
│   ├── base.py              imports every model — used ONLY by Alembic
│   └── session.py           async engine + get_db() FastAPI dependency
├── models/                 SQLAlchemy ORM models, one file per domain group
├── schemas/                 Pydantic request/response shapes + shared
│                             serializer functions (order_to_read,
│                             cart_item_to_detailed) reused by both REST
│                             endpoints and the LLM tool executor
├── services/                 ALL business logic lives here, never in
│   │                         endpoint functions. Endpoints are thin.
│   └── voice_service.py       Deepgram streaming STT connection + local
│                               pyttsx3 TTS — see "Voice layer" below
├── api/
│   ├── deps.py               get_current_user, get_current_staff_user,
│   │                          get_user_from_token (shared by both +
│   │                          the WebSocket voice endpoint)
│   └── v1/endpoints/          route handlers — auth, outlets, products,
│                               cart, orders, addresses, support, chat,
│                               staff, voice (the WebSocket endpoint)
├── llm/
│   ├── tool_schemas.py        every tool the model can call
│   ├── tool_executor.py       dispatches tool calls to services, scoped
│   │                           to current_user — THE security choke point
│   ├── system_prompt.py       behavior rules, security rules, tone
│   ├── safety_filter.py       belt-and-suspenders output regex check
│   ├── gemini_client.py       the manual tool-calling loop
│   ├── knowledge_base.json     REAL, authoritative general policy/support
│   │                            FAQ content from the founder (not product
│   │                            data — see "Known placeholders" for that)
│   └── knowledge_base.py       keyword-overlap search over the JSON above,
│                                backs the search_knowledge_base tool
└── utils/geo.py             Haversine distance for nearest-outlet lookups

migrations/                 Alembic — see "Migrations" below for the
                             two-step pattern used for anything needing a
                             hand-written migration (sequences, seed data)
```

## Non-negotiable architectural patterns — follow these for anything new

**1. Every user-scoped service function takes `user_id` as a parameter
derived from `get_current_user` (JWT) — NEVER from a request body, query
param, or LLM tool argument.** This is the core security guardrail of the
whole project. `get_profile` deliberately excludes the user's own `id`
from what it returns to the LLM, specifically so there's no way for the
model to leak it even if a prompt-injection attempt succeeds. Staff-only
functions (`get_order_by_id`, `set_order_status`) are the sole deliberate
exception, and they're gated by `get_current_staff_user`, never exposed
to a customer-facing route.

**2. Money-moving/state-changing operations are atomic transactions with
row-level locking.** See `order_service.checkout()` for the canonical
pattern: `SELECT ... FOR UPDATE` on every `outlet_stock` row involved,
validate everything BEFORE writing anything, single try/except around the
whole block with explicit `rollback()` on any exception. This exists to
prevent overselling when two customers order the last unit simultaneously.
Follow this pattern for any new inventory-affecting operation.

**3. Business rules live in data, not code.** `order_statuses` (modifiable/
cancellable flags), `products.max_qty_per_order` — these are DB rows so
they can change without a redeploy. Don't hardcode a status name's
behavior in Python; check the flag.

**4. Shared serializers, not duplicated formatting.** `order_to_read()` in
`schemas/order.py` and `cart_item_to_detailed()` in `schemas/cart.py` are
used by BOTH the REST endpoints and the LLM tool executor, so a customer
sees identical data whether they use `/docs` or chat. If you add a new
domain object the LLM needs to read, follow this pattern — don't write a
second formatter in `tool_executor.py`.

**5. Custom exceptions per service, caught explicitly at the endpoint
layer AND the tool-executor layer.** Never let a raw exception reach the
client or the LLM — always translate to an HTTPException (REST) or a
`ToolExecutionError` message (chat) that explains the situation in plain
language.

## Database

**Supabase, Session pooler connection** (port 5432, NOT the Transaction
pooler on 6543) — chosen because it supports prepared statements, which
`asyncpg` needs, and it's IPv4-compatible unlike the Direct connection.

**UUID primary keys everywhere** — deliberate, avoids leaking sequential
patterns/row counts. Where a human-readable reference is needed
(order numbers), there's a SEPARATE `order_number` integer column backed
by a Postgres sequence — the UUID stays internal-only.

**Migrations follow a two-step pattern** when something needs more than a
plain column change:
1. `alembic revision --autogenerate` for anything SQLAlchemy can diff on
   its own (new columns, new tables, relationship changes).
2. A **hand-written** migration (`alembic revision` with no
   `--autogenerate`, then manually edit `upgrade()`/`downgrade()`) for
   anything autogenerate can't safely produce — Postgres sequences,
   seed data (see `order_statuses` seed and the `order_number` sequence
   migration for examples). Always review autogenerated diffs before
   applying; strip out anything autogenerate got wrong (it has previously
   tried to add `order_number` as a plain column when the sequence needed
   to exist first).

## LLM layer

**Manual tool-calling loop, not the SDK's automatic function calling** —
`gemini_client.run_conversation_turn()` intercepts every single tool call
so it can execute against `current_user`, never blindly. This is
non-negotiable; don't switch to automatic function calling without
re-deriving how the security scoping would work.

**Model is configured via `settings.GEMINI_MODEL`, default
`"gemini-flash-latest"`** — an ALIAS Google maintains, not a pinned
version. A pinned version (e.g. `gemini-2.5-flash`) WILL eventually
404 when Google retires it — this already happened once. Don't repin
unless deliberately freezing behavior for a specific demo.

**Conversation memory is intentionally simple**: only the last 20 text
messages replay as history — no tool-call replay, no vector store. This
caused a real bug once (model re-added a cart item on "proceed to
checkout" because it only had its own paraphrase of prior state, not
verified truth). The fix — and the pattern to follow for any similar
issue — is a **grounding note**: freshly query real state and inject it
as a bracketed prefix on the current turn only (see
`chat_service._build_cart_grounding_note`), never trust history alone for
anything that must be exactly right.

**The greeting (`GET /chat/greeting`) is deliberately NOT an LLM call** —
every fact in it is already certain from the DB, so it's built with plain
Python string formatting. Don't be tempted to route it through Gemini;
that only adds latency, cost, and a chance of the wording drifting from
the actual data.

**Recommendations are prompt-driven, not hardcoded.** The system prompt
tells the model to call `list_products` and reason with its own general
knowledge — nothing about specific categories or products is baked into
any code. Keep it that way; hardcoding assumptions about the catalog was
explicitly ruled out by the founder/project owner.

**`search_knowledge_base` tool** answers general policy/support questions
(refunds, cancellations, wallet/cashback, privacy, account deletion) from
`app/llm/knowledge_base.json`, via simple keyword-overlap scoring in
`app/llm/knowledge_base.py` — no vector store, same simplicity call as
conversation memory. Scoped in the system prompt to general questions
only; product/stock/price/order questions stay on their existing tools.
Don't confuse this JSON with real product data — it has no SKUs.

**Category filters use `ILIKE`, not `==`** (`product_service.list_products`)
— the model guesses category strings from user phrasing and won't always
match the stored title-case values exactly. `tool_schemas.py`'s
`list_products` description also lists the actual valid categories so the
model has a real taxonomy to draw from instead of guessing blind.

**Delivery radius is actually enforced, not just stored.**
`Outlet.delivery_radius_km` existed from the start but was unused outside
the `check_product_availability` alternate-outlet fallback. Now
`outlet_service.get_nearest_outlet` returns a 3-tuple
`(outlet, distance_km, in_range)` — it prefers the nearest outlet that
can actually deliver (distance <= its own radius), not just the
geographically closest one, and reports `in_range=False` if none can.
`order_service.checkout` independently re-checks the *specific* chosen
outlet's radius against the address before writing anything
(`DeliveryOutOfRangeError`) — never trust that an earlier
`get_nearest_outlet` call was honored. Both paths exist because Local
Butcher genuinely only serves within Hyderabad; the system prompt tells
the model to treat a rejection here as a normal "we don't cover that
area yet" case, not an error to apologize awkwardly for.

**Chat can manage addresses now, but never sets coordinates.**
`add_address`/`update_address` (tool_executor.py) always pass
`lat=None, lng=None` to `address_service` — there's no geocoding in this
project, and the model must never fabricate coordinates for a text
address. `update_address`'s None-means-"don't touch" semantics make this
safe for edits (an address that already has coordinates via REST keeps
them). The consequence: `get_nearest_outlet` and `checkout` both now
treat missing coordinates as a hard stop for delivery
(`AddressMissingLocationError`) rather than silently skipping the range
check — that skip used to be the default and was a real gap once chat
could create addresses. Pickup orders are unaffected either way.

**Currency**: `settings.CURRENCY_LABEL` (default `"Rs."`), referenced in
both the system prompt and the grounding note. No currency is stored
anywhere in the schema — this is a pure display setting. Change it in
`.env` if the label needs to change, not in code.

## Voice layer

**`WS /api/v1/chat/voice/stream`** — real-time voice, no file upload.
The client streams raw linear16 PCM audio (16kHz, mono — see
`voice_service.open_transcription_stream`) continuously; Deepgram
transcribes it live and sets `speech_final=True` on the Results message
when it detects the customer actually finished a sentence (its own
endpointing, not manual silence-detection on our side). That final text
is handed to `chat_service.send_message()` completely unchanged — same
tools, same grounding notes, same security scoping. The reply comes back
over the same socket as both text and pyttsx3-synthesized audio.

**First WebSocket route in this project** — everything else is plain
REST. WebSocket auth can't reuse `get_current_user` directly (browsers
can't set an `Authorization` header on a WS handshake), so the JWT comes
in as a query param (`?token=...`) instead, resolved through
`get_user_from_token` in `app/api/deps.py` — extracted specifically so
REST and WebSocket auth share one JWT-to-User implementation rather than
duplicating the decode logic.

**pyttsx3 gets a fresh engine instance per call**, run via
`asyncio.to_thread` (`voice_service._synthesize_sync`). It wraps Windows
SAPI5 via COM, which is thread-affine — reusing one engine instance
across worker threads is not safe, but a new instance on whichever
thread runs it is. Don't "optimize" this into a cached/shared engine.

**Deepgram, not local Whisper** — chosen specifically because the ask
was genuine real-time transcription (interim results as the customer
talks), which a batch model like Whisper can't do without building
manual chunking/VAD, and which the browser's native SpeechRecognition
could do for free but only inside an actual browser page. Free tier,
account required (`DEEPGRAM_API_KEY` in `.env`, same pattern as
`GEMINI_API_KEY`). TTS deliberately stayed local/free (pyttsx3) — that
tradeoff wasn't reconsidered when the STT side moved to a cloud service.

**No frontend exists for this** — deliberately out of scope so far (see
`README.md`). Verified with a script that synthesizes a test utterance
with pyttsx3 and streams it into the socket in place of a live
microphone — a legitimate way to test the full loop without needing a
browser or real mic.

## Known placeholders — be upfront about these, don't let them pass as finished

- **ETA calculation** (`order_service._calculate_eta`) is prep-time +
  delivery-window heuristic from `.env` settings, not real logistics data.
- **No real staff app** — `role = "staff"` is set by direct DB edit only,
  no self-serve path (intentional, avoids a privilege-escalation hole via
  registration), but also means there's no UI for staff yet, just two API
  endpoints.
- **No promotions/offers table** — mentioned in the original feature list,
  not built.
- **Recommendation quality is bounded by real product data** — a
  placeholder catalog (16 products, Poultry/Meat/Seafood/Farm Eggs) is
  seeded via `migrations/versions/21c989a3600e_...` so recommendations
  are testable, but it's not the founder's real catalog. Swapping it in
  needs zero code changes.

## Testing conventions established so far

- Test data started as a couple of manually-inserted rows via Supabase
  Table Editor, since grown into proper seed migrations: 9 Hyderabad
  outlets with deliberately varied stock, 16 placeholder products, and a
  few demo addresses (see README "Current data"). Still not the
  founder's real catalog — that's a separate, deferred step.
- Every new step in this project has been verified with:
  1. A syntax check (`python -c "import ast; ast.parse(...)"` across
     `app/`) before considering anything done.
  2. Manual endpoint testing via `/docs` with a real Supabase-backed run.
  3. For chat-layer changes, checking actual server logs for the SQL
     statements that ran — not just trusting the reply text — since an
     LLM can describe an action in its reply without having actually
     taken it, or vice versa.

## Style notes

- Comments in this codebase explain *why*, not *what* — especially around
  security and data-integrity decisions. Keep that pattern.
- Prefer explicit custom exceptions over generic ones; prefer scoped
  service functions over convenience functions that accept broader access
  "just in case."
- Avoid overengineering: no Kubernetes, no microservices, single Postgres
  DB, minimal abstraction layers. This is an internship demo that needs to
  stay explainable in an interview, not a large production system.