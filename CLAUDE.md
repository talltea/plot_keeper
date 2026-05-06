# Plot Keeper — working notes

`DESIGN.md` is the canonical spec. Nothing in it is set in stone — it's
a working document and conflicts/updates land there as decisions are made.

## Status

Phase 0 complete (scaffold). See `IMPLEMENTATION_PLAN.md` for what's next.

## Stack

- **Backend:** Flask + plain `sqlite3`. Python 3.11+. Deps via
  `pip` + `venv` (no uv). Production via `waitress` under launchd; dev
  via `flask run`. SQLAlchemy/Alembic only if migrations get hairy.
- **Frontend:** Vite + Svelte PWA. Read-only offline; writes gated on
  laptop reachability. Write queue is a deferred enhancement.
- **Transport:** Tailscale serve from laptop. Tailscale is *transport*,
  not the trust boundary — app gates everything behind a password.
- **Auth:** Two roles, owner + viewer, argon2 hashes, cookie sessions.

## Operating principles (from design conversation)

- **Proof of concept first, polish later.** Phasing favors getting
  features in front of the user early; fancy architecture is deferred.
- **External APIs are draft generators, never authoritative.** Vision/OCR
  for seed packets, Perenual for plant catalog pre-fill — all return
  drafts the user reviews and edits. Manual entry is always available;
  failures fall back to it.
- **Photos are first-class.** Photo events, photos on zones, plants,
  seed packets, plant-kind catalog. Single `photo` table with polymorphic
  attachment.
- **Single-user assumption is real.** No conflict resolution beyond
  last-write-wins; the user is the only writer.
- **Sleeping-laptop UX is the central risk.** Mitigated by a planned
  write queue (deferred phase) + the user noting their laptop is almost
  always on.

## Decisions made

- **Framework:** Flask.
- **`plant.mode`:** keep one table with discriminator; mode-conditional
  columns are intentional, UI handles defaults.
- **`event.parent_event_id`:** dropped. `harvest_use` references its
  originating harvest only via free-text notes for now.
- **Write queue:** deferred to a future phase, listed under *Future
  expansions*.
- **Recall surfaces:** browse-the-journal model. Per-plant and per-zone
  timelines, plus a `/journal` chronological view across everything with
  filters. `this-week-last-year` is passive surfacing on the home
  screen, not the primary recall path.
- **Phenology UI:** table (rows=years, columns=headline event types),
  not SVG chart. Same component slot.
- **Pl@ntNet:** dropped. Photo plant-ID is not a planned feature.
- **Event taxonomy:** structured event types locked in for v1.
  Acknowledged risk: migrating to a tag-based model later costs more
  than the reverse, and we accept that.
- **Reminders interaction model:** intentionally unspecified; ack /
  snooze / annual-fire semantics need definition before phase 5
  implementation.
- **Photos:** first-class. `photo` + polymorphic `photo_attachment`
  replaces `event_photo`.
- **Pest UI:** per-plant "Pest history" tab — grouped list, no charts.
  No cross-plant view in v1.

## Still open

(Nothing pending from the design conversation as of last check-in.)

## Quickstart

First-time setup:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm install)
```

Run dev (single command, single port):

```sh
./scripts/dev.sh
```

Open http://localhost:5757 . Flask serves on :5757; Vite watches the
frontend sources and rebuilds `backend/static/` on every save. Ctrl-C
stops both. Backend changes auto-reload via `flask --debug`; frontend
changes need a manual browser refresh after Vite rebuilds.

Tests:

```sh
.venv/bin/pytest                 # backend smoke
(cd frontend && npm run check)   # svelte/ts type-check
./scripts/verify_phase0.sh       # live-server smoke
```

## Layout

- `backend/app.py` — Flask factory, routes are added here until phase 1
  splits them into `backend/blueprints/`.
- `backend/db.py` — sqlite3 connection helper + numbered-migration runner.
- `backend/migrations/000N_*.sql` — schema migrations, applied in order
  on startup. The runner records the applied version in `meta.schema_version`.
- `frontend/src/` — Svelte 5 + TS. `app.css` holds the field-notebook
  theme (paper background, fonts, ink/sage/rust/gilt palette).
- `data/` (gitignored) — `plotkeeper.db`, `photos/`, `backups/`.

## Conventions

- Svelte uses runes (`$state`, `$derived`, `$effect`). No legacy reactive
  `let` / `$:` syntax.
- Backend routes return JSON dicts; Flask handles serialization.
- Migrations are append-only; never edit a numbered file after it's been
  applied to a real DB.
