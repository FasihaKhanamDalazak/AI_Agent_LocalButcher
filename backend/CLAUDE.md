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
│   └── voice_service.py       Deepgram streaming STT connection + Aura
│                               TTS (REST) — see "Voice layer" below
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

**Text chat now runs through Deepgram's Voice Agent API too, not a direct
Gemini call** — `app/llm/deepgram_chat_client.py.run_conversation_turn()`,
called by `chat_service.send_message()`, same as the voice channels. The
original direct path, `gemini_client.run_conversation_turn()`
(google-genai SDK, `settings.GEMINI_MODEL` alias), is **kept intact but
unused** — a deliberate rollback path, not dead code to clean up, while
this replacement is still freshly built. Reason for the switch: text
chat's own `GEMINI_API_KEY` sits on the free tier's 20 requests/day, easy
to exhaust; routing through Deepgram's managed Google integration avoids
that key entirely (per Deepgram's docs, no API key of ours is involved
for that path).

**`InjectUserMessage`, not real audio, drives text chat's turns** — a
Voice Agent message type that skips straight to the "think" (Gemini)
step from plain text, no speech needed. `AgentV1Settings` still requires
a valid `audio` field (schema-mandated even though nothing is used), and
Deepgram still generates real reply audio server-side, which
`deepgram_chat_client.py` simply never sends anywhere and discards.
**Non-obvious, discovered only by testing, not documented anywhere**:
Deepgram still expects to receive *some* audio periodically even on this
text-only path — a simple no-tool reply completed fine without ever
sending audio, but a reply requiring a function-call round trip (think →
call out → wait → think again, taking longer) hit
`CLIENT_MESSAGE_TIMEOUT` before finishing. `_send_keep_alive_silence`
streams silent frames in the background for exactly this reason; removing
it would silently break every tool-using text reply, not just be a minor
inefficiency.

**A shared `deepgram_client.get_client()` factory exists specifically to
avoid a circular import** — `voice_service.py` needs
`chat_service.HISTORY_MESSAGE_LIMIT`, and `deepgram_chat_client.py` feeds
into `chat_service.py`, so if `deepgram_chat_client.py` got its Deepgram
client from `voice_service.py` (like it originally did, briefly, before
this was split out), the import cycle would be
`chat_service → deepgram_chat_client → voice_service → chat_service`.
`voice_service.get_client` is still re-exported from there for
`telephony_service.py`'s existing `voice_service.get_client()` call sites
— only `deepgram_chat_client.py` needed to stop going through it.

**Model is configured via `settings.VOICE_AGENT_GEMINI_MODEL` for this
path** (pinned `"gemini-2.5-flash"`, same as the voice channels — see
"Phone-call layer"), NOT `settings.GEMINI_MODEL`'s
`"gemini-flash-latest"` alias, because Deepgram's managed Google provider
rejects that alias. This is a real, accepted regression versus the
original direct-Gemini path: the alias's whole point was never needing a
manual repin when Google retires a version (already happened once) —
that protection is gone for text chat specifically now. `gemini_client.py`
still uses the alias for its own (currently unused) path.

**Verified end-to-end against the live Deepgram service before trusting
it, not just code review** — matching the same rigor as the voice channel
migrations: a simple no-tool reply, a tool-call reply (`get_cart`), a
multi-turn conversation (confirmed the model correctly recalled an
earlier turn — history preload works), `[[FOLLOWUPS: ...]]` chip parsing,
and Hindi/Hinglish (confirmed still works — unlike the voice channels,
nothing here ever touches spoken audio the customer hears, so Aura's
Hindi/Telugu gap doesn't apply; multi-language stays a genuine, real
advantage text chat keeps that the voice channels don't). Persistence
double-checked directly against the database each time — exactly the
right message count, no duplicates, matching the multi-fragment-reply
bug already fixed once for voice (accumulate `ConversationText` fragments
into one string before returning, don't persist per-fragment).

**Conversation memory is intentionally simple**: only the last 20 text
messages replay as history — no tool-call replay, no vector store. This
caused a real bug once (model re-added a cart item on "proceed to
checkout" because it only had its own paraphrase of prior state, not
verified truth). The fix — and the pattern to follow for any similar
issue — is a **grounding note**: freshly query real state and inject it
as a bracketed prefix on the current turn only (see
`chat_service._build_cart_grounding_note`), never trust history alone for
anything that must be exactly right.

**An unresolvable `conversation_id` starts a fresh conversation instead of
404ing.** A real customer's session sometimes carried a `conversation_id`
(e.g. handed off from a voice turn — see "Voice layer" below) that
`_get_or_create_conversation` couldn't find, hard-blocking every further
message with a 404 until they reloaded the page. The exact root cause
wasn't pinned down despite investigation (ref-based state across
`useChat.js`/`useVoiceChat.js` was suspected but not confirmed) — rather
than leave a real, reproducible way to hard-block a customer over an
edge case, the fix is resilience-based: if the given `conversation_id`
doesn't resolve to a conversation owned by this user, log a warning
(so a real fix can still be tracked down later) and silently start a new
one instead of raising. `ConversationNotFoundError` was removed entirely
as dead code once this landed. Verified against the real database: a
synthetic, definitely-nonexistent `conversation_id` no longer raises —
a fresh conversation is created and the turn completes normally.

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

**Delivery-only — pickup was removed as a concept, not just discouraged.**
`checkout` (REST `CheckoutRequest`, and the `checkout` tool every
chat/voice/call channel shares) no longer accepts a `fulfillment_type` at
all — `order_service.checkout()`'s signature dropped the parameter
entirely, `address_id` is now always required, and every order is
written with `fulfillment_type="delivery"` hardcoded. `Order.
fulfillment_type` the DB column is kept, unmigrated — `order_to_read`
still exposes it (always `"delivery"` now) and there was no need to drop
it just to remove pickup as a customer-facing choice. `_calculate_eta`
lost its pickup branch (single "ready by" time, no window) — it always
returns the delivery window now. All three system prompts and
`CartPanel.jsx` (which had a delivery/pickup toggle) were updated to
match — don't reintroduce a pickup option in only one of them if this
ever comes back.

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
could create addresses.

**A text-based Hyderabad fallback softens that hard stop** — a real,
customer-caught bug: a brand-new account's very first chat-added address
(no coordinates yet, which is EVERY chat-added address) blocked delivery
entirely, hard-blocking a core feature for exactly the kind of account
the founder will actually create. Both `outlet_service.get_nearest_outlet`
and `order_service.checkout` now treat an address whose text mentions
"Hyderabad" (case-insensitive substring match) as deliverable by the
first active outlet even with no coordinates on file — Local Butcher only
serves Hyderabad at all, so the text mention is treated as good enough
without a precise radius check. An address that doesn't mention
Hyderabad still hard-stops as before. Keep both call sites in sync if
this fallback changes. Verified against the real database both ways: a
Hyderabad-text address with no coordinates checked out successfully; a
non-Hyderabad address with no coordinates was still correctly blocked.

**Currency**: `settings.CURRENCY_LABEL` (default `"Rs."`), referenced in
both the system prompt and the grounding note. No currency is stored
anywhere in the schema — this is a pure display setting. Change it in
`.env` if the label needs to change, not in code.

## Voice layer

**`WS /api/v1/chat/voice/stream`** — real-time browser voice, no file
upload. Has a real frontend (`frontend/src/components/ChatInput/
ChatInput.jsx`'s mic button + `hooks/useVoiceChat.js`) — an earlier
version of this doc claimed otherwise; that was stale, not current fact,
verified directly against the frontend code before trusting it again.

**Architecture changed from "STT → chat_service → TTS as three separate
steps" to bridging Deepgram's Voice Agent API** (`voice_service.
bridge_browser_voice`) — the same STT+Gemini+TTS-in-one-session product
`telephony_service.py` uses for phone calls, not a coincidence: real
Gemini quota pressure and response latency on the old direct-call path
were the reasons for the switch, discovered in production use, not
theoretical. `app/api/v1/endpoints/voice.py` is now a thin endpoint
(auth, rate limit, accept, delegate, error redaction) matching
`calls.py`'s pattern — all the actual bridging logic lives in the service.

**Unlike the phone channel, the browser customer is ALREADY authenticated
(JWT) before the bridge ever starts** — no verification gate, every tool
available immediately via `PLAIN_JSON_TOOL_DECLARATIONS` (the same
converted-once declarations `call_tool_schemas.py` also builds on, minus
`verify_phone_number`, which is call-channel-only). Function-call dispatch
goes straight to `tool_executor.execute_tool(db, user, ...)` with the real
`User`, no special-cased tools, no not-verified branch — much simpler than
`telephony_service._dispatch_function`.

**Prior conversation history is preloaded when continuing an existing
conversation** (`_load_agent_history`, same `HISTORY_MESSAGE_LIMIT` as
`chat_service._load_history`, reshaped into Deepgram's plain
`{"type": "History", "role", "content"}` message format) — a customer can
switch from typing to talking mid-conversation (`ChatPage.jsx` shares one
`conversationId` between `useChat` and `useVoiceChat`), and without this
the Voice Agent would start with no memory of anything said before it.

**The existing frontend WS message contract needed zero changes** —
`useVoiceChat.js` still expects `interim_transcript`/`final_transcript`/
`assistant_reply` (with a complete `audio_base64` WAV blob, not a raw
stream)/`error` messages. Deepgram's Voice Agent doesn't work that way
natively (raw PCM chunks with no per-utterance framing, no interim/partial
transcript events at all), so the bridge reshapes it: `_wrap_pcm16_as_wav`
buffers one turn's raw audio and wraps it into a real WAV file with
Python's stdlib `wave` module right before sending; there's no
`interim_transcript` equivalent in this protocol at all (the frontend's
"Listening…" placeholder covers the gap with no code change, but live
word-by-word captions while speaking are gone — a real, accepted UX
regression, not an oversight).

**Two real bugs found only by testing against the live Deepgram service,
not from docs or code review** — see `_BrowserVoiceState`'s comments for
the full detail, worth reading before touching this file again:
1. Deepgram emits **multiple** `ConversationText(assistant)` fragments
   for what's one continuous spoken turn (e.g. "Your cart is currently
   empty." then "Is there anything I can help you add?" as two separate
   events, both audible in a single `AgentAudioDone`-bounded clip) — the
   first version overwrote instead of accumulating, so the displayed text
   silently dropped everything but the last fragment while the audio
   contained all of it. Fixed by concatenating fragments until the next
   `AgentAudioDone` flush, persisting the combined text as ONE Message row
   (matching `chat_service`'s one-row-per-turn convention), not one row
   per fragment.
2. Deepgram **also** emits a real `ConversationText` event for the
   configured static greeting (assumed it wouldn't; assumed wrong) — the
   first version separately preset the pending-text buffer with the
   greeting itself, which then got that event's text concatenated onto
   it, **duplicating the entire greeting** in what the customer saw and
   heard. `greeting_service.start_conversation_with_greeting` already
   persists the greeting as its own Message row (deliberately, so the
   model has it as context on the customer's real first turn — see that
   function's docstring); `has_pending_greeting` tracks "this is the very
   first non-empty audio flush of a new conversation" to skip a second,
   duplicate persist, rather than trying to detect the greeting by content.

**English-only** (`_LISTEN_MODEL = "flux-general-en"`, matching the call
channel) — a deliberate simplification made when this channel was built,
same underlying reason as the phone channel (Aura has no Hindi/Telugu
voice); text chat keeps full multi-language support unaffected.

**Sample rate is fixed at 16000 Hz, not configurable like the phone
channel's `CALL_AUDIO_SAMPLE_RATE`** — it's tightly coupled to
`useVoiceChat.js`'s hardcoded `TARGET_SAMPLE_RATE`, a frontend contract,
not an independent deployment knob the way Exotel's negotiated rate is.
Changing it needs a matching frontend change, not just a backend setting.

**Verified end-to-end against the real Deepgram service and real DB
state**, not just unit-level: a synthesized test utterance streamed in
realistic real-time-paced chunks (continuous silence after the utterance,
matching how a real open mic keeps streaming frames — an earlier test
version that went fully silent after the utterance triggered Deepgram's
own `CLIENT_MESSAGE_TIMEOUT`, a test-harness artifact, not a real bug)
produced a correct personalized greeting, correct transcription, a real
`get_cart` tool call through the actual `tool_executor`, a correctly
accumulated combined reply, valid playable WAV audio for both turns, and
exactly the right Message rows persisted (greeting once, user turn once,
assistant turn once — no duplicates).

## Phone-call layer

**`WS /api/v1/calls/stream`** (`app/api/v1/endpoints/calls.py`,
`app/services/telephony_service.py`) — real inbound phone calls via
Exotel's Voicebot/AgentStream applet, bridging to Deepgram's **Voice
Agent API** (`deepgram.agent.v1` — already present in the installed SDK,
no new dependency) the same way `voice_service.bridge_browser_voice`
bridges browser voice to it (see "Voice layer" above — this was the
*first* of the two channels built on Voice Agent, and the pattern proved
out here is exactly what motivated switching browser voice to match it
later). `telephony_service.bridge_call()` is purely a bridge: it relays
raw audio both directions between Exotel and Deepgram, and executes
whatever function calls Deepgram's agent decides to make. Neither voice
channel calls `gemini_client.py` — only text chat does; Gemini is
configured as Voice Agent's "think" provider directly (`type: "google"`)
for both.

**What's genuinely different about THIS channel versus browser voice**
(not the Voice Agent bridging itself, which is now shared): Deepgram's
Voice Agent speaks the *same* linear16 PCM Exotel uses at whatever sample
rate a live call reports (`CALL_AUDIO_SAMPLE_RATE`, discovered from a
real call's logs, not assumed — see below), so there's zero transcoding
on that leg; browser voice is fixed at 16000 Hz instead, tied to
`useVoiceChat.js`'s hardcoded rate. Audio framing differs too — Exotel
needs JSON+base64 media events in exact 320-byte-multiple chunks
(`_flush_aligned_audio`), browser voice just relays raw WS binary frames
directly, no alignment constraint. And authentication is the big one,
covered next.

**Authentication is fundamentally different from every other channel**: a
phone caller isn't a logged-in app user yet — there's no JWT. Exotel
itself is Basic-Auth'd on the WS handshake (`EXOTEL_BASIC_AUTH_USERNAME`/
`PASSWORD`, checked with `hmac.compare_digest`, fails CLOSED if unset —
see `calls.py._basic_auth_ok`), since Exotel has no HMAC request signing
like Twilio. Separately, the *caller* is authenticated mid-call: every
function in `call_tool_schemas.py` except `search_knowledge_base` requires
a verified phone number first. `verify_phone_number` — a call-channel-only
tool the text/browser-voice agent never sees — takes what the caller says
out loud and checks it via `auth_service.get_user_by_phone()`, which
normalizes loosely-formatted spoken numbers (`_normalize_phone`) into a
plain 10-digit number, no country code — **not E.164, deliberately, after
E.164 turned out to be a real bug**: verification worked on one real call,
then failed on the next with no code change in between, traced to the
stored `+91...` value and a caller-stated number disagreeing on whether a
country code was present. Since this project serves only the Indian
market (see "Tech stack" above), a country code added a mismatch surface
for zero actual benefit — `_normalize_phone` now just strips everything
but digits and takes the **last 10**, which correctly isolates the mobile
number regardless of whether "+91", "091", or nothing came before it, no
need to special-case any of them. `migrations/versions/
e2c525353f62_strip_country_code_from_phone_numbers.py` converted existing
`+91XXXXXXXXXX` rows; `UserCreate.phone`'s pattern
(`app/schemas/user.py`) enforces the new plain format at signup going
forward.

**A second, separate `_normalize_phone` bug, found right after the
country-code one, via the exact same raw/normalized logging**: the call
agent's `verify_phone_number` argument sometimes arrives as spelled-out
English words — `"Nine eight seven six five four three two one zero"`,
not numerals — consistently (every attempt, same rendering, not random
STT noise), despite the tool description saying to pass the number
through as heard. Stripping non-digit characters against an all-letters
string just produced an empty result, so every verification failed
silently until this was logged. `_normalize_phone` now walks every
digit-or-word token in the string (`_PHONE_TOKEN_RE`), converts
recognized number words (`_NUMBER_WORDS` — "zero"/"oh" through "nine")
to numerals, and drops anything else — handles pure numerals, pure
words, or a mix, uniformly, before taking the last 10 digits as before.
Verified against the real database with the exact failing string from
production logs, not just a plausible-looking test case.

Once verified, `telephony_service._dispatch_function` routes every other
call through the *exact same* `app/llm/tool_executor.execute_tool()` every
other channel uses — never a separate/parallel execution path — so the
core security guarantee in this file's rule #1 (`user_id` never trusted
from the model) holds here too: `tool_executor.execute_tool` is never
called with anything but a real `User` resolved from that phone lookup,
never from a model-supplied argument. This is deliberately **honor-system,
not caller-ID verification** — Exotel's `start` event does carry a
network-verified `from` field, but it's unused; the caller states their
own number instead. Simpler to build and what was actually asked for; see
README's "Known placeholders" if this needs hardening later.

**Dead air during tool calls — reported directly by a real caller, fixed
with `AgentV1InjectAgentMessage`.** A tool round trip (DB query + Deepgram's
own pipeline) takes a few real seconds; without any audio during that
gap, a phone call reads as dropped (unlike browser voice, which has a
visual "Thinking…" indicator — see "Voice layer" — there's no visual
equivalent over a phone line). Every `FunctionCallRequest` batch now gets
one spoken filler (`_FILLER_PHRASE`, `behavior="queue"` so it never
interrupts speech already in flight, just plays next) before dispatching.
`verify_phone_number` succeeding specifically ALSO gets a guaranteed
spoken confirmation injected directly — not left to the model's own
"think" step to remember, after a real report of the call sometimes
going fully silent right after verification instead of confirming it.
Both mechanisms verified directly against the live Deepgram service
(not just code review): `send_inject_agent_message` correctly produces a
`ConversationText` event followed by real audio bytes, no errors.

**"Rs." spoken as "R, S" — a self-contradicting prompt instruction, fixed
in both voice system prompts.** The original "Currency" section said to
*"say them with the '{settings.CURRENCY_LABEL}' label"* — literally
instructing the model to speak the abbreviation — while ALSO giving a
"three hundred and twenty rupees" example right next to it, a real
self-contradiction that let the model sometimes say "Rs." out loud,
which a text-to-speech voice reads letter by letter ("R, S"), not as a
word. Rewritten in both `call_system_prompt.py` and
`browser_voice_system_prompt.py` to unambiguously say NEVER speak
`{settings.CURRENCY_LABEL}` literally, always say "rupees" instead — no
example left that could be (mis)read as permission to do otherwise.
Text chat's `system_prompt.py` was never affected — showing "Rs. 320" as
written text is completely normal there, only speech has this problem.
Verified against the live Deepgram service for both prompts separately
(a live `FunctionCallRequest`/response round trip, not just a plain
reply): both correctly said "three hundred and twenty rupees," not
"Rs. 320."

**Tool declarations are converted once, shared by all three channels, not
duplicated** — `tool_schemas.py` itself now builds and exports
`PLAIN_JSON_TOOL_DECLARATIONS`, Deepgram's plain-JSON-schema function
format converted from the same `TOOL_DECLARATIONS` (google-genai typed
objects) text chat uses, via `_convert_schema_to_plain_json`/
`_convert_declaration_to_plain_json`. `call_tool_schemas.py` just adds
`VERIFY_PHONE_NUMBER_FUNCTION` on top for `CALL_TOOL_FUNCTIONS`;
`voice_service.py` (browser voice) uses `PLAIN_JSON_TOOL_DECLARATIONS`
directly, no verify function at all, since that channel's caller is
already authenticated. Originally lived only in `call_tool_schemas.py`
before browser voice needed the same conversion — moved to
`tool_schemas.py` at that point rather than duplicated a second time.

**Separate system prompt, not a shared/parameterized one**
(`call_system_prompt.py`, not a variant of `system_prompt.py`) — the two
channels differ enough (unauthenticated-until-verified, English-only,
spoken-not-written output, no `[[FOLLOWUPS]]` chips) that conditionals
inside one shared string would cost more clarity than the duplication
saves. Keep shared rules (security, tool-usage judgment) in sync by hand
across both; channel-specific rules only belong in the one that applies.

**English-only, not multi-language like text chat** — Deepgram's Aura TTS
voices are English/Spanish only, no Hindi, so even though Flux STT can
understand spoken Hindi, there'd be no way to answer back in it. Rather
than build an asymmetric "understands Hindi, always replies in English"
experience, the call channel stays English end-to-end; multi-language stays
a text-chat-only feature (see `system_prompt.py`'s "## Language" section).

**Gemini model is pinned** (`VOICE_AGENT_GEMINI_MODEL`, default
`gemini-2.5-flash`) — Deepgram's managed Google provider rejects the
`gemini-flash-latest` alias `GEMINI_MODEL` uses elsewhere in this project
(see "LLM layer" above for why that alias exists); this is a Deepgram
platform constraint, not a reconsideration of the alias-over-pin decision
for the rest of the app.

**Conversation persistence starts at verification, not at call start** —
`Conversation`/`Message` rows (channel="call") only get created once
`verify_phone_number` resolves a real user (`Conversation.user_id` is
`NOT NULL`, same as chat/voice); the general-Q&A portion of a call before
that point is never logged. A known, accepted gap for now, not a bug.

**Verified against real Exotel calls — two real bugs found and fixed this
way, not from docs alone**:
1. **Audio chunk misalignment** — Exotel requires media chunk sizes to be
   exact multiples of 320 bytes; Deepgram's TTS output arrives in
   arbitrarily-sized byte messages with no such alignment. Sending each one
   straight through caused audible glitching on a real call.
   `_flush_aligned_audio()` in `telephony_service.py` buffers and only ever
   sends whole 320-byte multiples, carrying remainders forward (and
   zero-padding the trailing remainder at call end so nothing is dropped).
2. **Sample rate mismatch** — this account's Voicebot Applet config UI has
   **no sample-rate selector at all** (contrary to
   developer.exotel.com/docs describing an 8k/16k/24k choice — that may be
   a higher-tier/enabled-feature thing), so it silently uses 8000 Hz
   regardless of what's requested. Assuming 16000 Hz (a reasonable docs-
   based default) produced a deep, slowed-down, "scary robotic" voice —
   generated audio played back at half its actual rate.
   `CALL_AUDIO_SAMPLE_RATE` is now 8000, confirmed correct by logging the
   real `start` event's `media_format.sample_rate` from a live call (see
   the `logger.info` in `_relay_exotel_to_deepgram`) rather than trusting
   docs. **If a different Exotel account/plan is ever used, re-verify this
   value from a live call's logs before assuming 8000 still applies** —
   don't just trust the dashboard UI or the docs.

**This account's Voicebot Applet also has no Basic Auth field** — same
"UI doesn't expose what the docs describe" gap as the sample-rate
selector, likely because Exotel's Stream/Voicebot Applet feature needs
support to explicitly enable it first (see README). `EXOTEL_REQUIRE_AUTH`
(default `true`) exists as an explicit, loudly-logged opt-out for this —
set `false` in `.env` only when the dashboard genuinely has no auth option
to configure, and flip it back once it does. Never remove the
`_basic_auth_ok` check itself as a "fix" for this.

**App-wide logging gap found and fixed while debugging this**:
`app/main.py` had no `logging.basicConfig(...)` call, so Python's root
logger defaulted to WARNING with no handler — every `logger.info(...)`
call anywhere in the app (not just telephony_service.py) was silently
discarded, even though uvicorn's own access/error logs still appeared
(uvicorn configures its loggers independently). Fixed once, at the top of
`main.py`, rather than routing around it — this affects every module's
logging, not just the phone-call layer.

## Order auto-progression

**`order_service.auto_progress_orders`**, run every
`AUTO_PROGRESS_CHECK_INTERVAL_SECONDS` (default 60s) by
`app/services/scheduler.py` via a background `asyncio` task started from
`main.py`'s `lifespan`. This project has no real staff/logistics operation
behind it — without this, every order would sit in `pending` forever,
which reads as a broken/unfinished feature to anyone testing the product,
not as an intentional placeholder. Same underlying motivation as the ETA
heuristic, just for status instead of a time estimate.

**Status is derived fresh from elapsed time every tick, never
incrementally stepped.** `_target_auto_status_code(elapsed_minutes)`
computes what status an order *should* be at purely from
`now - order.created_at`, using `AUTO_PROGRESS_PACKED_MINUTES` /
`_OUT_FOR_DELIVERY_MINUTES` / `_DELIVERED_MINUTES` (default 10/20/30) as
thresholds. A missed tick — the process restarts, Render's free tier
naps despite the keep-alive pinger, whatever — self-corrects on the very
next run instead of leaving an order stuck partway forever; there's no
persisted "next status" state to get out of sync with reality.

**Deliberately monotonic — comparing `OrderStatus.sort_order`, never
regresses a status backward.** A staff member can still manually advance
an order early via `PATCH /staff/orders/{id}` → `set_order_status`; the
next automatic tick computes what elapsed time alone would justify, and
if that's earlier in the sequence than what staff already set, the tick
is a no-op for that order rather than undoing the manual override. Proven
with a real test: staff-set `delivered` on a brand-new order (elapsed
~0 min, which alone would target `confirmed`) survives an immediate
automation tick unchanged. Automation only takes over again once real
elapsed time naturally catches up past wherever staff left it.

**`cancelled` and `delivered` orders are excluded from the query
entirely** (`OrderStatus.code.notin_(["delivered", "cancelled"])`) — both
are terminal states this function must never touch, so a customer's
`cancel_order` action can never be silently overwritten by the next tick.

**A single bad tick must never kill the loop** — `scheduler._run_forever`
catches and logs any exception from one iteration and keeps going; there's
no supervisor process that would otherwise restart a crashed background
task, so an unhandled exception here would silently stop all future
auto-progression for the rest of the process's life. Verified end-to-end
against real DB rows (not just unit-level): a real checkout followed by
one tick correctly moves `pending` → `confirmed`; a backdated 25-minute-
old order correctly jumps straight to `out_for_delivery` in one tick
(the self-correction case); the monotonic-no-regression case above.

**`AUTO_PROGRESS_ORDERS=false`** disables the whole thing without a code
change — flip this if real staff/logistics processing ever exists and
this becomes actively wrong instead of a helpful stand-in.

**Support tickets have the identical underlying gap, NOT given the same
treatment** — `create_support_ticket` files with `status="open"` and
nothing ever advances it (no chat tool, no staff endpoint). Deliberately
left alone: unlike an order's delivery, a real support issue's actual
resolution time isn't a knowable constant, so there's no equivalently
honest "N minutes later" rule to automate. Flagged in README's "Known
placeholders", not silently fixed with a fake timer.

## Hardening

**Rate limiting** (`app/core/rate_limit.py`) — `slowapi`, in-memory,
single-instance. A `default_limits=["60/minute"]` `Limiter` applies to
every route via `SlowAPIMiddleware`; auth and chat routes declare
stricter per-route limits with `@limiter.limit(...)` (needs a
`request: Request` param on the endpoint — that's how slowapi finds the
caller to key on). The voice WebSocket can't use the same decorator
(slowapi targets HTTP routes) — it has its own minimal connection-attempt
limiter built directly on the `limits` package slowapi itself depends on.
None of this survives a restart or works across multiple processes —
fine for one instance, would need Redis-backed storage before scaling
out.

**Global exception handler** (`app/main.py`,
`@app.exception_handler(Exception)`) — catches anything that isn't a
deliberate `HTTPException` (those already get FastAPI's normal handling)
and returns a generic `{"detail": "An unexpected error occurred."}`
instead of leaking a traceback or internal detail to the client. Always
logs the real exception server-side first (`logger.exception(...)`) — it
gets swallowed from the client's view, never from the logs. Verified
this actually works end-to-end via `TestClient` with a monkeypatched
service function raising — the middleware ordering with `SlowAPIMiddleware`
(a `BaseHTTPMiddleware`) is a known Starlette footgun for exception
handlers in general, so don't assume this still works after touching
middleware order — re-verify the same way if it changes.

## Known placeholders — be upfront about these, don't let them pass as finished

- **ETA calculation** (`order_service._calculate_eta`) is a heuristic
  window centered on `AUTO_PROGRESS_DELIVERED_MINUTES` (width
  `ETA_WINDOW_MINUTES`), not real logistics data — deliberately tied to
  the SAME number driving `auto_progress_orders`, not an independent
  heuristic. It used to be independent (separate `ORDER_PREP_MINUTES`/
  `DELIVERY_WINDOW_MIN_MINUTES`/`DELIVERY_WINDOW_MAX_MINUTES` settings,
  removed), which drifted into a real, customer-caught bug: the
  displayed ETA said ~80 minutes while the order was actually
  auto-marked delivered at 30. Every chat/voice/call channel reads the
  same `order.eta_start`/`eta_end` via the shared `order_to_read`
  serializer (rule #4 above), so this one fix corrected what all of them
  report — don't let these two numbers become independent again.
- **A second, separate ETA bug, found right after the one above**: even
  with `eta_start`/`eta_end` numerically correct, the phone-call agent
  was reading them as raw UTC datetimes and doing its own timezone
  conversion in speech — producing nonsense like "9 AM tomorrow" for an
  order due in 30 minutes the same afternoon. Same root cause pattern as
  the greeting used to guard against (see "LLM layer" — never trust the
  model with arithmetic on facts that are already certain): fixed by
  adding `OrderRead.eta_text` (`app/utils/time_format.py`'s `eta_text()`,
  the SAME function `greeting_service.py` already used correctly — moved
  there from a private copy so both share one implementation), a
  pre-formatted, already-local-time string every channel's system prompt
  is now explicitly told to read/speak verbatim, never compute from
  `eta_start`/`eta_end` itself. Verified end-to-end through the real LLM
  path, not just the field's value: asked a live (Deepgram-backed) text
  chat turn about a real order's ETA and confirmed the model's spoken
  reply matched `eta_text` exactly.
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