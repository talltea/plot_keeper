# Plot Keeper — Implementation Plan

**Premise:** the central risk is "will I actually log events on my phone in
the garden, and will the recall surfaces feel useful months later?"
Everything else is a bet that pays off only if that's a yes. So this plan
front-loads a working journal-and-recall loop, accepts manual entry
everywhere, and explicitly stops to evaluate before committing to the rest.

`DESIGN.md` is the canonical spec for *what* gets built. This document is
the order of *when*.

---

## Phase 0 — Scaffold (~1 day)

Just enough plumbing to start writing features.

- Flask app factory + `sqlite3` + numbered migration runner.
- Vite + Svelte scaffold; dev = `vite dev` with proxy to `flask run`;
  prod = `npm run build` served by Flask static.
- One smoke route end-to-end (`GET /api/ping` → JSON, rendered on home).
- No auth, no Tailscale, localhost only.

## Phase 1 — Core journal loop (~1 week) ⭐ *the bet*

Smallest thing that lets the user log events and see them back.

**Data:**

- `plant(id, name, kind_text, planted_at?, notes?)` — `kind_text` is free
  text. No `plant_kind` table yet. No `mode` / `display_name` / `zone`. No
  discriminator. Resist.
- `event(id, plant_id, occurred_at DATE, occurred_time TIME?, type, notes)` — types: `bloom,
  bud, fruit_set, harvest, harvest_use, pest_disease, prune, water,
  fertilize, observation, lesson, planted, removed`. No severity /
  treatment columns — they're notes for now.

**Surfaces:**

- `/` home: quick-capture shelf (recently-logged plants as tappable chips
  → straight to event form), plus a "this week last year" strip listing
  events whose `occurred_at` matches +/- 5 days of today's MM-DD in any
  prior year.
- `/plants` list, `/plants/new` form (name + kind + optional planted-at),
  `/plants/:id` detail (header + reverse-chrono event list + big
  "log event" button).
- `/journal` chronological list of all events with filters (type, plant,
  date range). Tap to jump to plant.
- Event form: type picker, date picker that *defaults to today but is
  freely editable* (backfill is a hard requirement, not a stretch goal),
  notes, save.

**Verification:** add 5 plants, log 20 events, half backfilled to last
year. Confirm the home strip surfaces the backfilled events on matching
days.

This phase is dogfoodable at a desk but not yet in the garden — that's
the next phase.

## Phase 2 — Phone access (2–3 days)

The bet only pays off if logging happens *in the garden*. So make mobile
real before adding more features.

- Owner password only (argon2 hash in `meta`). Defer viewer role.
- Cookie session, HttpOnly + Secure + SameSite=Lax, 90-day TTL.
  `session(id, role='owner', device_label, created_at, last_seen_at)`.
- `/login` route, rate-limit 10/min/IP.
- Bind to `127.0.0.1`. `tailscale serve https / http://127.0.0.1:8765`
  + a launchd plist that runs `waitress` on login.
- Minimal PWA manifest + apple-touch-icon so "Add to Home Screen" looks
  right on iOS. **No service worker yet** — keep it online-only.

**Verification:** add to home screen on phone, log a `bloom` event from
outside in the actual garden. If logging from the garden feels painful,
fix that before doing anything else.

## Phase 3 — Photos on events (3–5 days)

Logging without photos is half a journal. This is also the last cheap
feature before evaluating.

- `photo(id, path, thumb_path, taken_at, caption?)`
  + `photo_attachment(photo_id, target_kind, target_id)` polymorphic on
  `{event, plant}`.
- Backend stores original + 512px thumb (Pillow).
- Camera capture `<input type="file" capture="environment">`; event
  form gains optional photo.
- `photo` event type for cadence shots with no other observation.
- Per-plant gallery section (just a chronological grid).

**Defer:** named photo locations, framing-hint overlay, timelapse,
zone photos.

## Phase 4 — Phenology table (1–2 days)

Per-plant table: rows are years, columns are headline event types
(`bloom`, `bud`, `fruit_set`, `harvest`), cells hold the dates, plus a
right-most "this year vs. median" delta column. Same renderer powers
the inline header strip and the full Phenology tab. Value is small
with one year of data, real with two — fine, the table still renders.

## Phase 5 — Frost alerts + one-off reminders (5–7 days)

Highest-value proactive feature, and the user has now collected enough
data that "remember to cover the apricot" is a real pull.

- `weather_observation` / `weather_forecast` tables, daily Open-Meteo
  poll.
- Web Push (VAPID), subscribe from settings; iOS Safari ≥ 16.4
  PWA-installed.
- Frost push when overnight low ≤ 1 °C in next 48 h.
- `reminder(kind='one_off', ...)` only.
- **Defer:** annual / interval recurring, rain widget, dry-spell push,
  frost-date computation from history.

## Phase 6 — Zones, simple list kind only (3–5 days)

The plant list is getting long. Add `zone(id, name, kind='list',
sort_order)`, `plant.zone_id` nullable, `/zones` and `/zones/:id` list
views. Events can optionally scope to a zone (add `event.zone_id`
nullable, `CHECK (plant_id IS NOT NULL OR zone_id IS NOT NULL)` from
the design). Zone care strip: last mulched / amended / watered.

**Defer:** veg-bed grid, sketch zones with pins, photo locations.

## Phase 7 — Plant catalog (1–2 days)

Promote `plant.kind_text` to `plant_kind(id, name, emoji?, notes?)`.
Migrate existing values. Plant form picks an existing kind or creates
one inline. Catalog fields (days-to-harvest, spacing, etc.) all
deferred — none are needed for journal / recall.

## Phase 8 — Backups + viewer role + read-only offline (3–5 days)

Operational hygiene before the app holds enough years of data to mourn.

- `scripts/backup.sh` via SQLite backup API →
  `data/backups/plotkeeper-YYYYMMDD.db`. Time Machine carries it from
  there.
- Viewer password as second valid login, role on session, write buttons
  hidden / disabled.
- Settings: active sessions list with revoke.
- Service worker: NetworkFirst on GETs → "laptop unreachable" banner
  when offline, write buttons disabled. No write queue.

## Phase 9 — Veg-bed grid editor (5–7 days)

Now that zones exist and the app is proven worth keeping.
`zone.kind='veg_bed'`, `veg_cell`, `cell_planting` with counts. Grid
renderer, multi-plant cells (≤2 emojis + "…"), per-cell rotation
history.

## Phase 10 — Sketch zones + photo locations + timelapse (5–7 days)

`zone.kind='sketch'` with uploaded image and draggable named pins;
`photo_location` with framing-hint overlay; slider view.

## Phase 11 — Reminders & weather, full (3–5 days)

Annual + interval reminders, `rrule_json` + `season_window_json`. Rain
widget on home. Dry-spell push (off by default).

## Phase 12 — Pest history tab (2 days)

Add structured `cause`, `severity`, `treatment` columns to `event`
(still nullable, only filled for `pest_disease`). Group by cause on
plant page.

## Phase 13 — Planning (5–7 days)

Wishlist, seed inventory (**manual entry only** — no OCR), sowing
schedule from frost-date computation, next-season layout overlay on
veg-bed with rotation warnings.

## Phase 14 — External draft generators

In rough order of expected value:

1. **Vision / OCR for seed packets.** Highest payoff because seed-packet
   entry is tedious and has the worst manual-entry UX.
2. **Perenual** plant-kind pre-fill.
3. **Pl@ntNet** photo-ID for unknown plants.

All three are draft generators, all gated on the user supplying a key,
all degrade to empty manual form on failure.

## Phase 15 — Polish

Real PWA icons / theme, backup status surface in settings, write queue
with `client_event_id` idempotency (the deferred queued-writes
mechanism).

---

## What was deliberately deferred and why

- **`plant.mode` discriminator, `display_name`, `pin_x/pin_y`.** Pure
  organizational detail. Free-text plant names work fine until the
  veg-bed grid arrives in phase 9.
- **All API integrations.** The design itself says "API is a draft
  generator, never authoritative." Manual-first is faster and isolates
  feature-validation from third-party-API risk.
- **Veg-bed grid + sketch zones.** Highest-effort, lowest-on-the-
  critical-path-of-the-bet. The journal hypothesis doesn't need them.
- **Service worker / write queue.** Online-first; the laptop is almost
  always on. Read-only offline shows up in phase 8, write queue in
  phase 15.
- **Viewer role.** Single user can use the owner role until they want
  to share read-only access.

## Risks this plan accepts

- **No backwards-compatible migration story for the schema
  simplifications.** Phase 1 ships an intentionally lean schema; later
  phases add columns and tables that re-shape the model (e.g. promoting
  `kind_text` → `plant_kind`, adding `mode` to `plant`). The user is
  expected to be fine writing migrations that touch existing data — the
  alternative is upfront design work that defeats the point of this
  plan.
