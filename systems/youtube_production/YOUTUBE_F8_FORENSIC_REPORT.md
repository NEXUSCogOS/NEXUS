# YOUTUBE F8 FORENSIC REPORT
**NEXUS Federation F8 — 2026-08-28**

Per mission section 2: "Before changing anything, inventory the actual
YouTube production system... Do not rebuild a working production
capability." This report documents that inventory, completed BEFORE any
new code was written for F8.

## What exists, and where

A single canonical YouTube production estate at
`/Volumes/NEXUS/NEXUS_LOCAL/systems/youtube/` (external volume,
`NEXUS_LOCAL`), 72 top-level directories. No competing/duplicate YouTube
system exists under the canonical `NEXUS` repo (`${NEXUS_ROOT}`)
— `systems/` there has no `youtube` entry prior to this mission. Two
adjacent, historically-related but distinct items were also found and are
explicitly NOT part of this system:

- `systems/engineering_studio/studio_v3/platforms/youtube_automation.py`
  (528 lines) — a separate, older content-generation module with a
  `LegacySubsystemProxy` stub and `ContentGenerator.generate_from_trend()`.
  Already identified as out-of-scope downstream production code during F7
  (News's own forensic report); confirmed again here — not the active
  YouTube system, not reused, not duplicated.
- `${HOME}/.moved_Projects_20260503_084213/yt-engine-clean/` —
  a retired, manually-relocated project (`app/main.py`, `app/script.py`,
  its own `.env`) sitting in a path whose name (`.moved_Projects_...`)
  itself signals deliberate retirement. Not imported by, not referenced
  by, and not sharing any code path with the active
  `/Volumes/NEXUS/NEXUS_LOCAL/systems/youtube/` estate. Left untouched.

## The active scheduled automation: confirmed broken, not idle

The real, currently-installed system crontab runs three jobs against
`/Volumes/NEXUS/NEXUS_LOCAL/systems/youtube/runtime/entrypoints/youtube.py`:

```
0 * * * *  ... fetch_cycle    # NEXUS YouTube canonical hourly fetch
0 8 * * *  ... score_cycle    # NEXUS YouTube canonical daily scoring
# PUBLISH_GATE_DISABLED 30 10 * * * ... upload_cycle  # canonical upload 1
# PUBLISH_GATE_DISABLED 30 16 * * * ... upload_cycle  # canonical upload 2
```

**Two independent, load-bearing findings here:**

1. **The two active jobs (`fetch_cycle`, `score_cycle`) have never
   successfully executed.** `~/.local/logs/youtube_cron.log` contains 82
   lines, every one identical:
   `python3: can't open file '.../youtube.py': [Errno 1] Operation not
   permitted`. Confirmed via direct interactive read that the file exists,
   is well-formed, and is readable — this isolates the fault to the macOS
   cron daemon's own TCC/Full-Disk-Access permissions against the mounted
   external volume `/Volumes/NEXUS/`, not a missing or corrupt file, and
   not an application bug. Every single scheduled invocation on record has
   failed identically.
2. **The two upload jobs were already manually disabled by a prior
   operator**, via a `# PUBLISH_GATE_DISABLED` comment prefix, before this
   mission began. This is pre-existing evidence of deliberate
   publish-safety discipline already present in this estate. F8
   preserves this exactly as found — it is not re-enabled, not
   "fixed," and not treated as a bug.

## No real external channel exists

All four formal channel manifests
(`channels/channel_0{1,2,3,4}/channel_manifest.yaml`) show, identically:
`channel_name: UNASSIGNED`, `youtube_channel_id: UNASSIGNED`,
`publishing_enabled: false`, `build_authorised: false`. A separate,
richer `channels/channels_config.json` describes three *planned* channel
identities with real editorial detail (niche, tone, geography, brand,
color preset, trend source, seed keywords) — "DAT_AI Vision," "StockTipNews"
(referencing the real path
`${NEXUS_ROOT}/systems/sentinel/financial_intelligence.db`),
and "AI_Simplified" — but these are design/config artifacts, not
connected YouTube accounts. No `youtube_channel_id` anywhere in this
estate is a real, resolvable channel.

## No real credentials exist anywhere

Searched exhaustively for OAuth token files, `client_secret*.json`,
`credentials.json`, and any `.env` carrying real (non-example) YouTube API
values. Found only `deerflow_config/.env.example` (a template, no real
`.env` alongside it) and the config's own env-var indirection
(`YOUTUBE_CREDENTIALS_FILE`, `SLACK_BOT_TOKEN`, `SLACK_WEBHOOK_URL`), none
of which are set in this environment. `youtube_uploader.py`'s own
`_load_existing_token()` reads `Credentials.from_authorized_user_file(...)`
— no such token file exists on disk. `config.yaml`'s `data_sources`
section points `sentinel`/`datai` integration at `https://api.sentinel.local`
and `https://api.datai.local` — placeholder `.local` hostnames with no
real running service, confirming the "Sentinel integration" this system's
own `DELIVERY_SUMMARY.md` describes was never actually wired to the real
Sentinel SQLite database, despite `channels_config.json` separately
pointing at that real database path for a different purpose (editorial
seed context, not live API integration).

## Code is real, substantive, and largely unexercised — not mock

Every pipeline module under
`src/application/shorts/` (`pipeline.py`, `trending_sources.py`,
`data_fetch.py`, `media_intelligence.py`, `trend_detector.py`,
`render_queue.py`, `template_injector.py`, `approval_server.py`,
`youtube_uploader.py`) is genuine, non-trivial implementation code — real
`requests.get()` HTTP calls, a real `slack_sdk.WebClient` integration, a
real `subprocess`-based DaVinci Resolve CLI invocation, and a real,
complete Google YouTube Data API v3 client (`googleapiclient.discovery.build`,
OAuth token refresh, `upload()`, playlist assignment, monetization-metrics
fetch). This is categorically different from the entirely-fabricated
`media_intelligence_ingestion.py` found and correctly bypassed during F7
(`random.randint`/`random.choice`/`random.uniform` throughout, already
quarantined) — **this YouTube code is not mock, it is real code that has
never been successfully run end-to-end in this environment.**

Two hard, structural blockers, found by direct inspection, explain why:

1. **`RenderQueue`'s only render path shells out to DaVinci Resolve**
   (`/Applications/DaVinci Resolve/DaVinci Resolve.app/...`). DaVinci
   Resolve is **not installed on this machine** (confirmed:
   `/Applications/DaVinci Resolve*` does not exist). The render stage
   cannot function in this environment regardless of credentials.
2. **`Pipeline._init_modules()`'s approval gate requires
   `SLACK_BOT_TOKEN` and `SLACK_WEBHOOK_URL`.** Neither is set, so
   `self.approver = None` — and `run_upload_cycle()`'s first line of real
   logic is `if not self.approver: return` (logged as
   `"Approval server not initialized"`). Even if cron worked and
   DaVinci Resolve were installed, the upload cycle self-terminates
   before any render or upload is attempted, by the code's own existing
   design — a real, working fail-closed gate, not a bug.

## Zero real historical production output

- Both production databases (`data/youtube_intelligence.db`,
  `storage/databases/shorts_monetization.db`) show `videos: 0` — no video
  has ever been recorded as rendered, uploaded, or monetization-tracked.
  (`youtube_intelligence.db.channels` has 12 rows — competitor/reference
  channel metadata for intelligence-gathering, not owned channels.)
- No `.mp4`/`.mov` file exists anywhere in the 72-directory tree.
- The one artifact resembling a past end-to-end attempt,
  `Productions_Enhanced/AI_Simplified/test-topic-e2e-2026-08-02/`,
  contains only `job.json`, `metadata.json`, `thumbnail_spec.json` — a
  planning/spec stage only, no rendered media, no thumbnail image.

## What this means for `DELIVERY_SUMMARY.md`'s claims

That document (dated 2026-08-15) asserts "Autonomous Publishing: Enabled,"
"No human approval required," and "Status: Production-Ready." Its own
deployment checklist, in the same file, shows
`[ ] YouTube API credentials setup (requires user)`,
`[ ] Real TTS engine configuration (requires user)`,
`[ ] Sentinel integration setup`, `[ ] Production deployment` — all
unchecked. Combined with the findings above, the "Production-Ready"
claim is not supported by the actual runtime state of this estate. F8
does not treat that document as ground truth; ground truth is this
report.

## What this environment DOES genuinely have available

Checked directly, not assumed: `ffmpeg` (Homebrew, present), `Pillow`
11.3.0 (present), macOS `say` (present, real local TTS, no cloud
credentials required), `gTTS`/`pyttsx3` (present). These are real,
locally-available, credential-free capabilities distinct from the
existing pipeline's DaVinci-Resolve/cloud-TTS assumptions, and are what
F8's own render step uses (see YOUTUBE_PRODUCTION_E2E_EVIDENCE.md) — a
genuinely different, minimal, real render path, not a revival of the
existing broken one.

## Conclusion — do not rebuild, do not reuse the broken paths

The existing estate is not rebuilt. F8 does not touch
`/Volumes/NEXUS/NEXUS_LOCAL/systems/youtube/` and does not re-enable the
`PUBLISH_GATE_DISABLED` cron lines. A new, minimal, real institution
(`systems/youtube_production/`) is built instead, structured the same
way Sentinel (F5), Librarian, and News Intelligence (F7) were: a typed
schema, a generic-contract institutional report, real (not mocked)
component implementations bounded to what this environment can actually
execute, and an absolute, structurally-enforced publication boundary —
see YOUTUBE_CAPABILITY_MATRIX.json for the category-by-category
classification this report supports.
