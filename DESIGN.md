# Plot Keeper — Design

A personal, multi-year garden companion. Single-user, single-household.

## Property profile

- ~100 sq ft veg bed (square-foot style; interplanting is common)
- A few flower beds around the property
- Front yard: fruit trees, berry bushes, flowers
- A handful of house plants

## Goals (priority order)

1. **Long-term journal & memory.** Capture structured observations across years
   and surface them when relevant. "When did the apricot bloom in '23/'24/'25?"
   "What did I do about peach-leaf-curl last time, and did it work?" "What was
   happening this week last year?"
2. **Light proactive nudges.** Frost alerts, custom reminders, and gentle
   "this week last year" surfaces. Not a todo app for plants.
3. **Planning future plantings.** Sowing schedule, seed inventory, wishlist,
   next-season layout overlay (with crop-rotation hints).

## Non-goals

- Yield optimization / serious quantity tracking. Quantities are optional
  throughout.
- Generic plant-care database lookup. The personal catalog is the source of
  truth; we only consult external services for narrow tasks (Pl@ntNet for
  unknown-plant ID).
- Multi-user, sharing, social, or cloud-tenanted features.
- Growing Degree Days, iNaturalist nearby, sun-hour modeling. Considered and
  deferred — interesting but not on the critical path. Revisit if the gap is
  felt in practice.

---

## Architecture

The original idea was a static PWA on GitHub Pages with manual JSON export.
That was rejected during design because iOS Safari evicts IndexedDB after ~7
weeks of inactivity, which is unacceptable for a multi-year journal. Instead:

```
Phone (installed PWA, Safari)  ──Tailscale (HTTPS)──▶  Laptop server
                                                       │
                                                       ├─ FastAPI (Python)
                                                       ├─ SQLite (file on disk)
                                                       └─ photos/ on disk
```

- **Backend**: Python 3.11+ / Flask / SQLite. Plain `sqlite3` is enough for
  v1; revisit if migrations get complex. Photos as files on disk, served via
  Flask's `send_from_directory`. Migrations via `meta.schema_version` +
  numbered SQL files. Dev: `flask run`; production (under launchd): `waitress`.
- **Frontend**: Vite + Svelte, served by Flask in production (single deploy
  unit). PWA via `vite-plugin-pwa` (Workbox under the hood).
- **Service worker**: cache GETs (NetworkFirst with cache fallback) to give a
  **read-only offline** mode. Writes are gated on connectivity — when offline,
  the action UI is disabled with a "laptop unreachable" banner. No write queue
  in v1 (the laptop is almost always on); a queued-writes-with-replay
  mechanism is a planned later-phase addition (see *Future expansions*).
- **HTTPS / exposure**: `tailscale serve` on a fixed port. App binds to
  `127.0.0.1` only; only Tailscale exposes it. PWA install + Web Push both
  require HTTPS, so this is load-bearing.
- **Auto-start**: launchd plist runs the server on login.
- **Backups**: nightly job snapshots `plotkeeper.db` via the SQLite backup API
  into a `backups/` folder; Time Machine carries it from there.

External services (all optional, keyless where possible):

- **Open-Meteo** — frost forecast + historical for derived average frost
  dates; precipitation forecast + recent observed precipitation for the
  rain widget.
- **Vision/OCR provider** — seed-packet photo → structured fields (variety,
  days-to-harvest, sowing depth, spacing, source). Default: Anthropic
  vision API (user supplies a key in settings).
- **Perenual** (or equivalent genus-info API) — plant-kind catalog
  pre-fill (sowing windows, spacing, depth, common pests). User-supplied
  key, free tier sufficient.

All external integrations follow the same rule: **API is a draft
generator, never authoritative.** Extracted fields land in a form the
user reviews; failures fall back to manual entry. See *Graceful
degradation* below.

### Auth (revised from earlier "no auth")

Tailscale is the *transport*, not the boundary. The app gates everything
behind a password.

- Two roles: **owner** (full read+write) and **viewer** (read-only — sees
  everything, write actions are hidden / disabled with a tooltip).
- Each role has its own password (stored as argon2 hashes in `meta`).
- Single cookie-based session per device, long-lived (90 days), HttpOnly +
  Secure + SameSite=Lax. Session table records role + device label so the
  owner can revoke a viewer session from settings.
- Rate-limit failed logins (10/min/IP). No account recovery — laptop
  access is the recovery path.

### Graceful degradation

Every external integration must declare its failure UX. If you can't
state what the user sees when the dep is down, don't ship the dep.

| Dep | Trigger | User sees | Fallback |
|---|---|---|---|
| Open-Meteo (frost) | Network / 5xx / quota | Stale-cache banner with last-good date | Use cached forecast; no push fires until fresh data |
| Open-Meteo (rain) | Network / 5xx / quota | "Rain data unavailable" on home strip | Hide rain row; nothing else affected |
| Vision/OCR (seed packet) | Network / 401 / quota | "Couldn't read packet" toast | Empty draft form opens for manual entry; packet image still saved |
| Perenual | Network / 401 / quota | "Look-up failed, fill in manually" | Manual entry; existing values untouched |
| Web Push | iOS not installed / unsubscribed | Settings banner: "push not active" | In-app reminder list; no audible alert |
| Tailscale | Phone off-tailnet | PWA shows "laptop unreachable" | Read-only cached views; queued writes (when implemented) |

Common rules:
- All external keys live in `meta`, settable from `/settings`. Empty key = feature visibly off, never a crash.
- All external responses cached locally; UI distinguishes "live" vs "stale (since DATE)".
- Server-side calls have a 5 s timeout and a single retry with backoff.

---

## Data model (SQLite)

```
zone(id, name, kind, sketch_image_path, sort_order)
  kind ∈ {veg_bed, sketch, list}
  – veg_bed gets the grid editor
  – sketch zones store an uploaded image with named pins
  – list zones are pure lists

veg_cell(zone_id, row, col)
  Only present for veg_bed zones.

plant_kind(id, name, emoji, scientific_name, notes,
           days_to_harvest_min, days_to_harvest_max,
           sow_indoors_weeks_before_last_frost,
           direct_sow_weeks_around_last_frost,
           transplant_weeks_after_last_frost,
           spacing_in, depth_in,
           fertilize_schedule, common_pests,
           source, source_overridden_at)
  Personal catalog. Reused across plantings and years. Catalog fields
  (days-to-harvest through common_pests) start NULL. The plant-kind
  editor offers a "Look up" action that calls the genus-info provider
  (default: Perenual API, user-supplied key) and returns a draft
  pre-fill the user reviews and saves. Variety-specific values
  (days-to-harvest in particular) come from the seed-packet OCR flow,
  not from the genus-info provider, since varieties differ widely.
  External lookup is never authoritative — it's a draft generator.
  `source ∈ {api, user}`; `source_overridden_at` records when the user
  diverged from the API value.

plant(id, plant_kind_id, mode, display_name, zone_id, pin_x, pin_y,
      planted_at, removed_at)
  mode ∈ {individual, planting}
  – individual: apricot tree, each blueberry bush (display_name set)
  – planting: a row of carrots = one "planting" (display_name typically
    NULL; UI falls back to plant_kind name + planted_at)
  pin_x/pin_y locate the plant on a sketch zone (NULL for veg-bed plants
  and for purely list-tracked zones).
  Several columns are mode-conditional and may be NULL accordingly
  (display_name, pin_x, pin_y). Not enforced at the schema level — UI
  handles defaults.

cell_planting(cell_id, plant_id, count)
  Many-to-many. Multi-plant cells with optional counts. The veg-bed UI reads
  and writes the world through this table.

event(id, plant_id?, zone_id?, occurred_at DATE, occurred_time TIME?,
      type, severity, treatment, notes)
  CHECK (plant_id IS NOT NULL OR zone_id IS NOT NULL)
  type ∈ {
    bloom, bud, fruit_set,
    harvest, harvest_use,
    pest_disease,
    prune, water, fertilize, mulch, amend,
    observation, photo, lesson,
    planted, removed,
  }
  occurred_at is a DATE; occurred_time is optional and set on real-time
  entries (NULL when backfilling). Backfilling is a hard requirement.
  – fertilize / mulch / amend are zone-or-plant-scoped: a row of compost
    tea on the apricot is a plant event; a wheelbarrow of mulch on the
    veg bed is a zone event. Zone pages surface "last mulched" and
    "last amended" prominently.
  – `photo` is a pure photo log with no other observation — useful for
    "what did the bed look like this week" cadence shots. Any other
    event type can also carry photos via `event_photo`.

photo(id, path, thumb_path, taken_at, caption, photo_location_id?)
  First-class. Attached polymorphically via `photo_attachment`.

photo_attachment(photo_id, target_kind, target_id)
  target_kind ∈ {event, plant, zone, seed_inventory, plant_kind}
  Many-to-many: one photo can be pinned to multiple targets (e.g. a
  single zone hero shot also linked to a `photo` event). Lookups are
  always (target_kind, target_id) → photos.

photo_location(id, zone_id, name, framing_hint)
  Named "same-spot" anchors for the timelapse view; referenced from
  `photo.photo_location_id`.

reminder(id, kind, plant_id?, zone_id?, title, notes, fires_at,
         rrule_json, season_window_json)
  kind ∈ {one_off, annual, interval}

seed_inventory(id, plant_kind_id, year_acquired, quantity, source,
               germination_test_date, germination_rate, notes,
               packet_image_path, packet_ingest_status)
  packet_ingest_status ∈ {none, pending, draft, confirmed}
  – `none`: hand-entered, no packet photo
  – `pending`: photo uploaded, OCR running
  – `draft`: OCR returned fields; user has not confirmed
  – `confirmed`: user reviewed and saved
  When the user is in the seed-add flow they can either type fields or
  snap a packet photo; the photo path goes through the vision provider,
  fields land as a draft form, user edits and saves.

wishlist(id, plant_kind_id?, name, notes, link)

planning_layout(id, year, zone_id, snapshot_json)
  Proposed next-season cell assignments. Commit copies into cell_planting
  and creates `planted` events on the chosen date.

meta(key, value)
  location lat/lon, vision/OCR API key,
  schema_version, push subscription, owner_password_hash,
  viewer_password_hash.

session(id, role, device_label, created_at, last_seen_at, revoked_at?)
  role ∈ {owner, viewer}. Cookie value is the session id.
```

### Event types — notes

- `bloom`, `bud`, `fruit_set`, `harvest` — the phenology backbone. Drive both
  the multi-year chart and the "this week last year" view.
- `harvest_use` — what the harvest became. Free-form notes (recipe, method,
  outcome, "ate fresh", "gave to neighbor"). v1 has no formal link back to
  the originating `harvest`; the user's notes can reference the date.
  A future `pantry_item` table layered on top would add structured
  linkage (see *Future expansions*).
- `pest_disease` — feeds the pest atlas. Severity + treatment fields are
  structured; cause and notes are free text.
- `prune`, `water`, `fertilize` — care log. Mostly used by reminders, but
  recorded so "what did I last do for the apricot?" is answerable.
- `observation` — catch-all freeform note attached to a plant or zone.
- `lesson` — end-of-season reflections; tagged for easy recall.
- `planted`, `removed` — lifecycle bookends. `planted` is auto-created when
  committing a planning layout.

---

## Frontend surfaces

Quick-capture flow (the most-used path): **plant → event type → save**, 2–3
taps. The home screen biases toward this.

Top-level routes:

- `/login` — password entry. Single field, two valid passwords (owner
  and viewer) resolve to different roles; identical UI either way.
- `/` — home: today's frost-warning banner if any, weather strip showing
  last rain (date + mm) and next forecast rain (when + mm), quick-capture
  shelf with recent/favorite plants, this-week-last-year strip, pending
  reminders.
- `/zones` — list of zones; tap to drill in.
- `/zones/veg-bed` — square-foot grid editor. Cells render up to 2 plant
  emojis + "…" if more; tap a cell to see contents and per-cell crop-rotation
  history. Multi-plant cells with optional counts.
- `/zones/:id` — sketch or list zone. Sketch zones show the saved image with
  draggable named pins. Every zone view shows a care strip: last mulched
  (date + material from notes), last amended / fertilized (date + what),
  last watered if tracked. One-tap log buttons for mulch / amend /
  fertilize / photo at the zone level.
- `/plants/:id` — plant detail page:
  - Header: kind, mode, planted date, current location.
  - Tiny inline phenology strip (recent years × headline events).
  - Recent events.
  - Tabs: **Timeline** (all events, filterable) · **Phenology** (full
    multi-year table) · **Pest history** (past `pest_disease` events
    grouped by cause, with severity, treatment, and free-text outcome
    inline) · **Photos** (gallery + timelapse when a photo location is
    pinned).
- `/journal` — chronological browse of all events across plants and
  zones. Filters by event type, plant, zone, and date range. Infinite
  scroll back through years. Tap any event to jump to its plant or
  zone. Lessons get visual emphasis so they surface above routine
  events. The "I tried something cool last May, what was that?" entry
  point.
- `/plan` — sowing schedule (driven by frost dates), seed inventory, wishlist,
  next-season layout overlay on veg bed with rotation warnings.
- `/settings` — location, vision/OCR key, push subscription,
  backup status, owner/viewer password management, active sessions list
  (revokable). Viewer role sees this page in read-only form (no key
  reveal, no password change, no session revoke).

Reusable components worth pre-naming:

- `VegBedGrid` (read + edit modes)
- `PhenologyTable` (powers both the inline strip and the full table)
- `EventForm` (one form, switches fields by event type)
- `PhotoLocationCapture` (camera + framing-hint overlay for same-spot shots)
- `ReminderForm` (one-off / annual / interval)

---

## Phenology table

Per-plant table. Rows are years, columns are headline event types
(`bloom`, `bud`, `fruit_set`, `harvest`), cells hold the date(s) of that
event in that year, plus a right-most "this year vs. median" delta
column. No SVG, no charting library.

The same renderer powers the inline strip on the plant header
(compressed to recent years and the headline event types) and the full
table on the Phenology tab.

---

## Photos & same-spot timelapse

Camera capture via `<input type="file" capture="environment">`; backend stores
the original plus a 512-px thumbnail.

Same-spot timelapse: the user defines a `photo_location` (e.g., "Veg bed from
NE corner") with a "framing hint" — a faded ghost of the previous photo
overlaid on the camera viewfinder when capturing the next one. This is the
trick that makes timelapses align without a tripod. Renders as a slider /
animation on the plant or zone page.

Photo opportunities are first-class throughout the app, not only inside
typed observations:

- Every event-form has an "add photo" affordance — typed or freeform.
- The dedicated `photo` event type is for cadence shots ("the bed this
  week") with no other observation attached. Fast path from home.
- Zone pages have a "snap a photo of this zone" button that creates a
  zone-scoped `photo` event in one tap.
- Plant pages have the same on the header.
- Seed packet capture in the seed-inventory flow stores the packet image
  alongside extracted fields (see *Planning*).

A simple per-plant and per-zone chronological gallery covers the read
side; same-spot timelapse is the only specialized view.

---

## Planning

- **Sowing schedule.** Compute average last/first frost dates from Open-Meteo
  historical (50% probability over past 20 years of daily mins). Seed packets
  declare "weeks before/after last frost" or absolute dates. Calendar is
  derived; nothing stored except the seeds.
- **Seed inventory.** Packets, germination tests, decay across years. Add
  flow: snap a photo of the seed packet → vision provider extracts
  variety, days-to-harvest, sow depth, spacing, source — fields land as a
  draft form pre-filled from the OCR; user reviews and confirms. Original
  packet photo is kept (`packet_image_path`) for future reference. If the
  vision call fails, the same form opens empty for hand entry.
- **Wishlist.** Loose backlog; can be promoted into a sowing entry or planting.
- **Next-season layout.** Planning overlay on the veg-bed grid for a future
  year. Renders rotation warnings ("this cell had nightshades 2 of last 3
  years"). Commit action copies layout into `cell_planting` and creates
  `planted` events on the chosen date.

---

## Reminders & weather

Web Push (works on iOS Safari ≥ 16.4 once the PWA is installed to the home
screen). Server holds the push subscription; sends notifications via VAPID.

- One-off date reminders.
- Annual recurring (date or date range — "early February").
- Interval recurring within a season window ("every 2 weeks Jun–Sep").
- Light seasonal nudges from past entries: when this week last year had ≥3
  events of a kind on a given plant, surface that on the home screen
  (passive — not a push).

Frost alerts: server polls Open-Meteo daily, stores forecast, fires push when
overnight low ≤ 1 °C in the next 48 h.

Rain tracking: same daily poll fetches recent observed precipitation
(past 14 days, daily totals) and the next 10 days' forecast. Cached in
`weather_observation` / `weather_forecast` tables keyed by date. Surfaces:

- Home strip: "Last rain: 2026-04-30 (8 mm). Next: 2026-05-07 (12 mm
  forecast)."
- Plant / zone pages can surface "days since last rain" inline next to
  the watering log so it's obvious whether you need to water.
- Optional push when a dry spell ≥ N days is forecast to continue (off
  by default; toggleable in settings).

---

## Critical files

```
plot_keeper/
├── DESIGN.md                      # this file
├── backend/
│   ├── requirements.txt           # flask, waitress, httpx, pillow,
│   │                              # pywebpush, argon2-cffi
│   ├── app.py                     # Flask app factory + blueprint registration
│   ├── db.py                      # sqlite3 connection, migrations
│   ├── migrations/0001_init.sql   # schema
│   ├── auth.py                    # owner/viewer login, sessions, role guards
│   ├── blueprints/
│   │   ├── zones.py
│   │   ├── plants.py
│   │   ├── events.py
│   │   ├── photos.py
│   │   ├── planning.py
│   │   ├── reminders.py
│   │   └── weather.py
│   ├── services/
│   │   ├── weather.py             # Open-Meteo client + cache
│   │   ├── perenual.py            # genus-info lookup for plant_kind pre-fill
│   │   ├── vision_ocr.py          # seed-packet → structured fields
│   │   ├── push.py                # Web Push send
│   │   └── frost_dates.py         # historical → average frost dates
│   └── tests/                     # pytest + Flask test_client
├── frontend/
│   ├── package.json               # vite, svelte, vite-plugin-pwa
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.ts
│   │   ├── app.svelte
│   │   ├── routes/                # home, zones, plants, plan, settings
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── VegBedGrid.svelte
│   │   │   ├── PhenologyTable.svelte
│   │   │   ├── EventForm.svelte
│   │   │   ├── PhotoLocationCapture.svelte
│   │   │   └── ReminderForm.svelte
│   │   └── service-worker.ts
├── scripts/
│   ├── install-launchd.sh
│   ├── backup.sh
│   └── tailscale-serve.sh
└── data/                          # gitignored
    ├── plotkeeper.db
    ├── photos/
    └── backups/
```

---

## Verification

End-to-end smoke (re-run after each relevant phase):

1. `flask --app app run --port 5757` on the laptop; hit
   `http://localhost:5757`.
2. `tailscale serve https / http://127.0.0.1:5757`; phone Safari opens via
   tailnet, lands on `/login`, owner password lets through; "Add to Home
   Screen" → installs as PWA. Open in a private window with the viewer
   password → write buttons hidden / disabled. Owner revokes the viewer
   session from settings → next viewer page load bounces to `/login`.
3. Add a sketch zone, upload an image, drop a pin "Apricot", create the
   apricot as an individual plant. Log a `bloom` event today.
4. Open the plant page → event in timeline; phenology dot appears.
5. Add a `bloom` event dated 2025-04-19 → phenology table shows two years.
6. Create veg bed (10×10), assign tomato + basil to A1 with counts (1, 3),
   carrots in row C with count 16. Verify cell display + tap-to-edit.
7. Log a `harvest` event on tomatoes; chain a `harvest_use` event ("made
   sauce, freezer, lesson: needed more reduction"). Verify both appear on
   the plant timeline; child event renders nested under its parent.
8. Set lat/lon in settings; confirm forecast loads, including last-rain
   and next-rain values on the home strip; subscribe to push from the
   phone. Simulate frost: set `WEATHER_FIXTURE_PATH=tests/fixtures/forecast_frost.json`
   and reload the weather job — the fixture returns a forecast with an
   overnight low ≤ 1 °C in the next 48 h, expect a push within 30 s.
   Same fixture mechanism works for `WEATHER_FIXTURE_PATH=tests/fixtures/forecast_dryspell.json`
   to exercise the dry-spell push.
8a. Snap a seed packet photo in the seed-inventory flow → draft form
    appears with extracted variety / days-to-harvest / spacing; confirm
    saves a row with `packet_image_path` set.
9. Create a one-off reminder for tomorrow → push arrives at the right time.
10. Disconnect phone wifi → app still loads, plant pages browseable, the
    `+ event` button shows offline state and is disabled. Reconnect → button
    re-enables.
11. Run `scripts/backup.sh` → `data/backups/plotkeeper-YYYYMMDD.db` exists
    and opens cleanly with `sqlite3`.

Tests:

- Backend `pytest`: services (frost-date computation, push payload shape)
  and routers (TestClient + fixture DB).
- Frontend `vitest`: chart math, rotation-warning logic.
- One Playwright scenario: log an event end-to-end against a running server.

---

## Future expansions (not v1)

- **Pantry items + decrement.** Promote `harvest_use` outcomes of type
  "preserved" into rows in a `pantry_item` table (jam jars, frozen bags,
  dehydrator trays). One-tap "use 1" decrements; the home screen can answer
  "do I have any apricot jam left?"
- **Recipe / method records.** Reusable across years and harvests, tied to
  plant kinds. "Show me everything I've made with blueberries before."
- **Variety performance view.** Cross-year comparison of which varieties of
  the same plant kind produced the best preservation outcomes.
- **Surplus nudges.** Passive home-screen surface: "you've harvested 3× last
  year's zucchini already; here's what you did with the surplus last time."
- **Write queue with replay.** Today writes are gated on connectivity. A
  later phase: queue offline writes in IndexedDB keyed by `client_event_id`
  UUID, replay FIFO on reconnect; server treats `client_event_id` as a
  unique key (idempotent). Photo uploads use the same queue. Failed
  replays surface in a "needs attention" tray.
- **Cross-plant pest view.** A property-wide `/pests` route — "show me
  every aphid event across all plants." Per-plant pest history covers
  the immediate need; this is for higher-level pattern recognition.
- **Growing Degree Days.** Open-Meteo hourly historical + forecast; predict
  bloom/harvest/pest pressure dates from accumulated heat. Strong fit with
  the phenology data we'll already be collecting.
- **iNaturalist nearby observations.** "Recently observed near you" panel —
  blooms, pests, fruit. Anticipates pest emergence.
- **Sun-hour modeling.** SunCalc.js-driven; given a marker on a sketch and
  approximate obstacles, render modeled sun-hours per month per spot.
- **Hardware dashboard.** Soil-moisture sensors via Web Bluetooth or an MQTT
  bridge. Probably overkill at this scale.

---

## Open implementation choices

- **DB access.** Plain `sqlite3` + Pydantic in v1; revisit if migrations get
  hairy (consider SQLAlchemy core only if needed).
- **Auth.** Two-role password gate (owner + viewer). Argon2 hashes,
  cookie sessions, revokable per device. Tailscale is transport, not
  trust boundary. See *Auth* under Architecture.
- **Vision/OCR provider.** Default Anthropic vision API (user supplies
  key). Alternative path with Tesseract.js client-side considered and
  rejected: poor on stylized seed-packet typography, larger PWA bundle,
  worse field-extraction quality. Revisit if cost or rate-limits bite.
- **Sketch-zone editor.** v1 stores a static uploaded image with pins
  positioned by drag. If freehand drawing in-app is wanted later, add a small
  canvas editor.
