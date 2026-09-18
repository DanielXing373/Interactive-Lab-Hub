# Bird Clock — Progress & Collaborator Guide

**Last updated:** 2026-09-18  
**Package path:** `Lab 2/bird_clock/`  
**Purpose of this doc:** handoff for a teammate. Read this before editing code or art so we do not break a working deliverable.

---

## 1. What this project is

**Bird Clock** is a Flappy-Bird–style game on a Raspberry Pi 5 + Mini PiTFT (240×135 landscape), also runnable on desktop for development.

It is **not** primarily a hardcore skill game. The main deliverable is a **promotional / homework video** about time: seasons, festivals, and “time is not just a number.” Game feel should support **spectacle and story**, not tournament difficulty.

### Core player loop

| Mode | Behavior |
|------|----------|
| **IDLE** | Auto-pilot flies; HUD shows **real wall clock** (date / hour / minute / second as feather tokens). No pickups (would desync the clock). |
| **PLAY** | Manual flap; score is sexagesimal-style from play time; pickups spawn; obstacles denser for look. |
| **DYING / AFTER_DEATH** | Fall off screen → wait → A return idle / B retry (swapped vs start/flap during play). |

### Hardware vs desktop

- **Pi:** `python3 -m bird_clock` (or `--pi`) from `Lab 2/`
- **Desktop sim:** `python3 -m bird_clock --desktop` from `Lab 2/`
- Auto-detects Blinka / board when possible; override with flags.

**Important:** always `cd` into `Lab 2` (directory name has a space). Running from the repo root will not find the package.

```bash
cd "/path/to/Interactive-Lab-Hub/Lab 2"
python3 -m bird_clock --desktop
```

On Pi, if `__main__` is missing from git (see `.gitignore` / `__*` rules historically), force-add `__init__.py` / `__main__.py` or run:

```bash
python3 -c "from bird_clock.main import main; main()"
```

---

## 2. Repository layout (what matters)

```
Lab 2/
├── bird_clock/                 # ← the game package
│   ├── main.py                 # entry, backend choose
│   ├── game.py                 # modes, input, loop glue
│   ├── bird.py / pipe.py / items.py / collision.py
│   ├── auto_pilot.py           # IDLE flight
│   ├── renderer.py             # draw order
│   ├── sprites.py              # PNG load, scale, optional 3-slice
│   ├── scenes.py               # season/festival pools + weights
│   ├── config.py               # ALL tunable numbers (change here first)
│   ├── clock_display.py / score.py
│   ├── hardware.py / desktop.py
│   ├── assets/<skin>/          # art + skin.json
│   ├── 素材与宣传清单.xlsx      # asset + shot + feature tracker (Chinese UI)
│   └── PROGRESS.md             # this file
├── make_templates.py           # generate placeholder skin folders
├── sim_pickups.py / sim_scenes.py   # headless regressions
├── shot_*.py                   # offline PNG strips for eyeballing
└── README.md                   # Lab 2 course README (assignment), not this game’s design doc
```

Planning spreadsheet: `bird_clock/素材与宣传清单.xlsx`  
Sheets include: 说明, 故事线, 素材表, 画布规格, 宣传镜头, 功能清单, 进度.

---

## 3. Hard conventions (do not casually break)

### 3.1 Coordinates

- **World:** origin bottom-left, +y up (physics / bird / pipes).
- **PIL / screen:** top-left, +y down. Conversion only in `renderer.py` (`world_to_screen_y`).

### 3.2 Tunables live in `config.py`

Do **not** hardcode sizes, speeds, or spacings in spawn/render logic. Change `PipeConfig`, `ItemConfig`, `HudConfig`, etc.

**Current spectacle-oriented defaults (approx.):**

| Setting | Value | Intent |
|---------|--------|--------|
| Obstacle width clamp | 36–58 px | ~1.8× old 20–32; real width follows PNG aspect |
| Play spacing | 48–68 | ~4–5 obstacles on screen |
| Idle spacing | 44–62 | denser auto-fly look |
| Idle / play start speed | 34 / 40 | slightly snappy scroll |
| Entrance anim | 0.75 s, peak 1.13 | cosmetic stab-in (not collision) |
| Bird | 8×8 | hitbox = draw box for greybox; sprite may differ later |
| Pickup hitbox / art | 16 / 26 | art can overlap walls; idle never spawns pickups |

### 3.3 Obstacle **width follows PNG aspect**

Spawner (`pipe.py` `_fit_aspect`) reads each slot’s source PNG `width/height`, then sets:

`width ≈ solid_height × (src_w / src_h)`  

clamped to `min_width`–`max_width`.  
**Do not** independently randomize width and height again — that caused flat/skinny trees.

### 3.4 Sprite scaling (current)

**Default: uniform nearest-neighbor stretch** of the whole PNG to the obstacle rectangle.

Vertical 3-slice (preserve canopy/trunk/roots) still exists in `sprites.py` but is **off** unless the slot sets `"slice": true` plus `stretch_start` / `stretch_end` (or legacy `cap` / `cap_at`). Leave the old fields in `skin.json` if you want; they are ignored without `"slice": true`.

### 3.5 Scenes = art folder + spawn lottery

`scenes.py` defines scenes (spring, summer, christmas, …). Each has:

- `skin` → `assets/<skin>/`
- `weights` → which of the 7 collision kinds may spawn (`rect_bottom`, `rect_top`, `tri_bottom`, `ground`, …)
- Weight **0** = never spawn (avoids greybox holes for unfinished art)
- **RECT_BOTH (bilateral trees) is intentionally off** for seasonal trees (looked wrong). Keep it off unless redesigning.

**While a ground strip covers the spawn column, only top-only kinds may spawn.** If the scene has no top-only art, spawn skips (retry soon) — never invent an undeclared shape.

Scene selection order:

1. Manual override (IDLE: press **B / flap** to cycle scenes — filming cheat)
2. Calendar date (festivals by `(month, day)`, seasons by month)
3. Fallback (`SceneConfig.fallback`, usually `spring`)

Lunar festivals (春节 / 元宵) are **not** auto-computed; set dates by hand or use the cheat button.

### 3.6 Skins (`assets/<name>/skin.json`)

Example spring (live):

- `rect_bottom` / `rect_top`: `cherryblossom.png` (top uses `"flip_y": true`)
- Missing files → greybox shapes; game must still run
- `"file"` may be a string or a list; **only the first file is used today** (extra names reserved for later variants)

**Do not** put art only under `bird_clock/*.png`. Always place under `assets/<skin>/` and reference from `skin.json`.

### 3.7 Pickups

- **Play only.** IDLE must never spawn pickups (wall clock integrity).
- Placement stays inside the flight corridor; conflict with late-spawned pipes is resolved at the right edge.
- Score: play uses `add_bonus`; IDLE wall clock must not jump from bonuses.

### 3.8 Entrance animation

Cosmetic only. Collision and auto-pilot always use **final** geometry. Ground strips do not play the stab-in anim.

### 3.9 Buttons

| Context | A (start gpio) | B (flap gpio) |
|---------|----------------|---------------|
| IDLE | Start play | **Next scene** (cheat) |
| PLAY | — | Hold to flap |
| After death | Return IDLE | Retry |

Desktop: map keys in `desktop.py` (see that file).

---

## 4. Current progress (as of 2026-09-18)

### Done (engine)

- [x] Game modes: idle / play / death / after-death
- [x] Mixed obstacles: bi/uni rect & triangle, continuous ground strip
- [x] Triangle + wrapped AABB collision (`collision.py`)
- [x] IDLE auto-pilot with multi-obstacle corridor constraints
- [x] Feather HUD clock + `+N` score popups
- [x] Dynamic left-edge hints
- [x] Death-screen button swap + idle countdown
- [x] Pickups (play-only) + reachability placement
- [x] Scene system + weighted spawn pools
- [x] Skin / sprite pipeline (sky, far parallax, obstacles, pickups, bird)
- [x] Aspect-correct obstacle sizing
- [x] Uniform sprite stretch (default); optional 3-slice kept dormant
- [x] Obstacle entrance animation (timing tunable)
- [x] Desktop + Pi backends
- [x] Headless sims: `sim_pickups.py`, `sim_scenes.py`

### Done (content / production)

- [x] Asset & promo shot tracker workbook
- [x] Spring skin with real cherry blossom obstacle art (standing + hanging)
- [x] Placeholder templates for other spring layers (sky/far/etc. still mostly placeholders)

### Not done / thin

- [ ] Full seasonal / festival art packs (summer–asian_games mostly missing → greybox or incomplete)
- [ ] Pickup art per season (butterfly etc. still placeholders)
- [ ] Bird sprite polish
- [ ] Fixed-size obstacles (Christmas tree as non-stretched silhouette) — discussed, not implemented
- [ ] Visual variants (`file` list random pick) — format reserved, not active
- [ ] Re-enable `"slice": true` 3-slice if uniform stretch looks wrong on some assets
- [ ] Full-screen FX (fireworks, poem drift) — tracker G04
- [ ] Scene transitions — G05
- [ ] True auto season-by-clock beyond current month/date tables — G06 partial
- [ ] Audio — deferred (can be post on the video)
- [ ] Promotional video edit + homework short video shooting

### Tracker feature IDs (workbook)

| ID | Topic | Status (approx.) |
|----|--------|------------------|
| G01 | Pickups | Done (play-only) |
| G02 | Skin / resource packs | Basic done |
| G03 | Background layers | Done (sky + far) |
| G04 | Full-screen FX | Not started |
| G05 | Transitions | Not started |
| G06 | Clock-driven season | Partial (month/date) |
| G07 | Sprite cache | Done |
| G08 | Audio | Deferred |
| G09 | IDLE scene skip | Done (B button) |

---

## 5. Art pipeline (for the teammate doing assets)

### Style target

Pixel art closer to **Stardew / Terraria**: hard edges, limited palette, no anti-aliasing. Generate large, then **nearest-neighbor** downscale.

### Where files go

```
bird_clock/assets/<skin_name>/
  skin.json
  *.png
```

Copy spring as a template:

```bash
cd "Lab 2"
python3 make_templates.py summer   # placeholder PNGs + skin.json
# then replace files and edit skin.json / scenes.py weights
```

Point the game at a skin via the **scene’s** `skin=` field in `scenes.py` (not a lone `SkinConfig.name` anymore).

### Slot meanings

| Slot | Role |
|------|------|
| `rect_bottom` | Standing column (trees, sprouts) |
| `rect_top` | Hanging (same art + `flip_y` is OK) |
| `tri_bottom` / `tri_top` | Triangle silhouettes (pyramid, tree, ice) |
| `ground` | Horizontal tile strip (must tile left↔right) |
| `sky` | Full 240×135, opaque |
| `far` | Parallax band; **must tile horizontally** |
| `pickup.coin` | Collectible art |
| `bird` | Player |

### Collaboration rule for art

1. Prefer **adding** new files under `assets/<skin>/` and editing `skin.json`.
2. Avoid rewriting `pipe.py` / `auto_pilot.py` / `collision.py` unless fixing a clear bug.
3. After adding a slot to a scene’s **weights**, ensure the PNG exists or expect greybox.
4. Keep IDLE free of score side effects.

---

## 6. Scripts & how to use them

Run from `Lab 2/` unless noted.

| Script | Role |
|--------|------|
| `python3 -m bird_clock --desktop` | Play / accept art |
| `python3 make_templates.py [skin]` | Scaffold `assets/<skin>/` |
| `python3 sim_pickups.py` | IDLE no pickups, play placement, entrance margin |
| `python3 sim_scenes.py` | Every scene: idle survival + no undeclared shapes |
| `python3 shot_frames.py` | Grab play frames to `/tmp/bird_shots/` |
| `python3 shot_entrance.py` | Entrance animation filmstrip |
| `python3 shot_slots.py` | One controlled frame per obstacle slot |

If you change spawn weights, spacing, or collision: run **`sim_scenes.py`** and **`sim_pickups.py`** before committing.

---

## 7. Safe collaboration zones

### Relatively safe to edit

- `assets/**` and `skin.json`
- `scenes.py` weights / dates / labels (keep invariants above)
- `config.py` numeric tuning (document why in commit message)
- Tracker xlsx / this PROGRESS.md
- New helper scripts under `Lab 2/` (don’t break package imports)

### High risk (ask / pair first)

- `auto_pilot.py`, `collision.py`, `pipe.py` spawn + ground constraints
- `game.py` mode machine / IDLE pickup ban
- `sprites.py` stretch / slice semantics
- `hardware.py` (Pi-only breakage)

### Suggested git hygiene

- Small commits: “art: spring cherryblossom” vs “engine: aspect sizing”
- Do not force-push `main`
- Do not commit secrets; Pi WiFi notes stay local
- Watch `.gitignore`: `__*` once blocked `__main__.py` — use `git add -f` if needed

---

## 8. Near-term plan (priority)

Given limited time, recommended order:

1. **Finish one filmable skin (spring)** — sky, far, ground strip, butterfly, bird; keep cherryblossom.
2. **Shoot homework clips** (hardware, idle auto, buttons, death, feather clock) — tracker V19–V23; pickups need **manual play**.
3. **One more skin for the promo** (e.g. christmas or winter) if time — not all seasons.
4. **Promo edit** — seven-act script is in the xlsx 故事线; do not block on perfect gameplay.
5. Optional: re-enable `"slice": true` only if uniform stretch ruins a specific asset.

Out of scope unless free time: audio in-engine, lunar calendar, perfect auto-pilot under extreme density, bilateral trees.

---

## 9. Quick “did I break it?” checklist

After your change:

```bash
cd "Lab 2"
python3 -m compileall -q bird_clock
python3 sim_pickups.py
python3 sim_scenes.py
python3 -m bird_clock --desktop
```

Manual smoke:

- IDLE: clock ticks; B cycles scene names on the hint; no pickups.
- PLAY: cherryblossom up and down; ~4–5 columns visible; pickups only here.
- Death: B retries, A returns; countdown on return hint.

---

## 10. Contact / ownership notes

- Design direction: video-first, spectacle density, seasonal storytelling.
- Engine conventions above are intentional; “simplifying” spawn or IDLE scoring usually causes subtle regressions.
- When unsure, prefer **config + skin.json** over rewriting systems, and leave a note in this file or the xlsx 功能清单.

---

*This document describes the bird_clock subtree of Interactive Lab Hub Lab 2. Course lab instructions remain in `Lab 2/README.md`.*
