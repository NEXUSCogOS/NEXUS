# YOUTUBE PRODUCTION E2E EVIDENCE
**NEXUS Federation F8 — 2026-08-28**

Real, captured execution of `test_f8_full_production_loop_real_synthesis`
(`tests/f8/test_f8_youtube_production_institution.py`). No conclusion
chosen in advance -- this test re-runs F6's own real four-process chain
fresh (real DAT.AI planning-zone data, real Librarian + Sentinel
analysis) and reacts to whatever the real result is.

## Real upstream synthesis (F6 chain, re-run fresh for this mission)

```
executive_conclusion_class = PARTIALLY_SUPPORTED
```

(the same real Dong Nai planning-zone / industrial-park-ticker analysis
described in FEDERATION_F6_IMPLEMENTATION_REPORT.md, re-executed live)

## Real editorial suitability decision (mission.py::assess_editorial_suitability)

`PARTIALLY_SUPPORTED` is in `_EDITORIALLY_SUITABLE_CLASSES` ->
`suitable=True`.

## Real channel selection

`event_headline` = "Vietnamese industrial-park and real-estate sector
stocks near a government planning zone adjacent to Long Thanh
International Airport", `event_keywords` = ["stocks", "market", "real
estate", "investing", "trading"] -- an honest description of the actual
Sentinel entity-mapping content (5 real tickers: KBC, SZC, GVR, IDC,
LHG, all real-estate-sector). Matched against the REAL, pre-existing
`channels_config.json` identity "StockTipNews" (niche: "stock market
finance trading investing").

## Real DelegationProposal (first ever at GENERATE_INTERNAL in this federation)

```
recipient   = youtube_production
authority   = GENERATE_INTERNAL
mission_id  = <trigger_id>-mission-y
delegation_created = True
```

## Real production mission

```
production_mission_id = 685d56a9-9d4a-5d5b-8770-22af7b53d5a8
terminal_state (initial) = RECEIVED
```

## Real evidence pack + script + fact-check

- Evidence pack built from the real synthesis's `supporting_findings` /
  `contradictory_findings` (Sentinel's real DERIVED_METRIC entity-mapping
  findings for KBC/SZC/GVR/IDC/LHG).
- Script generated with FACT/ANALYSIS/INTERPRETATION/HYPOTHESIS/
  EDITORIAL_TRANSITION segments, each factual segment carrying exactly
  one `claim_id`.
- Anti-hallucination check: 0 violations (every numeric token traced to
  the evidence pack).
- Fact-check: every claim reached SUPPORTED/PARTIAL; 0 UNSUPPORTED
  claims in the final script.

## Real render (macOS `say` + Pillow + ffmpeg -- NOT the pre-existing DaVinci-Resolve-dependent path)

```
render_id    = deterministic uuid5(production_mission_id, script revision 1)
output_hash  = c02a27d838c342bbc9b41ff66c68b2b0c6a2be70135951dbf381678e0f39894c
output_path  = /Volumes/NEXUS/NEXUS_LOCAL/f8_media_output/f8_685d56a9-9d4a-5d5b-8770-22af7b53d5a8/render_rev1.mp4
duration     = 34.663311 seconds
resolution   = 1280x720
codec        = h264/aac (ffmpeg, confirmed via ffprobe: codec_name=h264, codec_name=aac)
storage      = EXTERNAL (mounted volume, not internal Mac disk)
```

File existence, real duration>0, and a real 64-hex-char sha256
output_hash are all asserted directly by the test (not merely printed).

## Real InstitutionalReport, ingested through the generic kernel

`kernel.ingest_report()` (the SAME ingress DAT.AI/Librarian/Sentinel/News
use) accepted the report on the real run
(`ingress_accepted=True`). `publication` component:
`lifecycle=NOT_COMMISSIONED`.

## Real process identity

Three distinct OS PIDs this real run: `PID_A=30659 PID_B=30660
PID_C=30680` (Process A: mission creation: Process B: production;
Process C: NEXUS ingestion) -- confirmed distinct in the test itself.
(An earlier captured run of the same test produced `PID_A=29221
PID_B=29222 PID_C=29240` with `production_mission_id=
dec28261-1021-5e32-bc36-f84920de64b7` -- both are real, independently
reproducible runs of the same real mechanism, not a single cherry-picked
result.)

## Terminal state

```
final production_mission terminal_state = READY_FOR_PUBLICATION_AUTHORIZATION
```

Never `PUBLISHED`. No upload API was invoked at any point in this chain.
