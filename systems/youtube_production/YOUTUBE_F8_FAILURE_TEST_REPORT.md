# YOUTUBE F8 FAILURE TEST REPORT
**NEXUS Federation F8 — 2026-08-28**

## Section 27: Unsupported-claim negative control

Fixture-only, per the mission's own allowance for negative controls
(mirrors F7's contradiction test convention). An evidence pack whose only
finding establishes nothing (`NO_MATERIAL_CROSS_DOMAIN_EFFECT_
ESTABLISHED`-equivalent, tagged `UNKNOWN:`), plus a script segment
attempting to smuggle in a sensational, unbacked FACT claim ("This stock
is guaranteed to triple in value next month!") whose `claim_id` matches
no real evidence item.

**Result:** `fact_check_script()` classified it `UNSUPPORTED`,
`action_taken=REMOVED`; the segment does not survive into the revised
script; the surrounding editorial-transition segments (`intro`) are
preserved unchanged. **PASS.**

## Section 28: Missing-rights negative control

An asset with `rights_status=UNKNOWN` (`rights.make_unknown_rights`)
alongside a real `GENERATED` asset. `rights.enforce_rights()` correctly
excludes the `UNKNOWN` asset from the usable set and keeps the
`GENERATED` one usable. `usable` flag on the `UNKNOWN` record is `False`
by construction — never flipped. **PASS.**

## Section 31-equivalent: real defects found and fixed during construction

1. **Module bare-name collision (`schema`/`storage`).** This
   institution's core modules follow the SAME bare-filename convention
   every prior institution uses (`schema.py`, `storage.py`,
   `institutional_report.py`) — but `news_intelligence/` (F7) ALSO ships
   `schema.py` and `storage.py`. Importing both packages' same-named
   bare modules directly into the ONE shared pytest process (as this
   test file's fixture originally did) poisoned `sys.modules['schema']`
   for whichever suite ran second, breaking 5 of `test_f7_news_event_
   driven_cognition.py`'s own tests with `ImportError: cannot import
   name 'SourceClass' from 'schema'` when the full federation suite ran
   together (they passed individually). **Fixed:** the F8 test file no
   longer bare-imports `youtube_production`'s own modules at module
   scope; the two negative-control checks above and the mission-state
   read now run in their own fresh subprocesses/plain sqlite3 queries,
   exactly like every other cross-institution boundary in this
   federation. Full federation suite re-verified green after the fix
   (151 passed, 1 pre-existing skip).
2. **Broken local ffmpeg (environment, not code).** `ffmpeg` was
   confirmed present during ground-truth (YOUTUBE_F8_FORENSIC_REPORT.md)
   but its actual invocation failed: `dyld: Library not loaded:
   libx265.215.dylib` -- a genuine, pre-existing Homebrew inconsistency
   (x265 had been upgraded to 4.3/`libx265.217.dylib` without ffmpeg
   being relinked against it). **Fixed** via `brew reinstall ffmpeg`
   (relinks against the current x265; verified `ffmpeg -version` and a
   real render both succeed afterward). Disclosed here as a real,
   observed, environment-level failure and repair, not silently worked
   around.
3. **`authority/model.py`'s own unit test suite hardcoded the old
   ceiling.** `tests/unit/test_authority_model.py` asserted
   `MAX_GRANTABLE_AUTHORITY_THIS_PHASE == ANALYSE` and that
   `GENERATE_INTERNAL` always exceeds the ceiling -- both correct before
   this mission, both now Instructed by this mission's own deliberate
   change. **Fixed:** updated to assert the new ceiling
   (`GENERATE_INTERNAL`) and that only levels strictly above it
   (`MODIFY_REVERSIBLE` and up) are refused; added a new test confirming
   `GENERATE_INTERNAL` is now accepted. This is exactly the "visible,
   deliberate edit" `authority/model.py`'s own docstring anticipated,
   not a silent loosening.

## What was NOT built as a dedicated failure test

- **Render backend failure (e.g. corrupt audio input):** not exercised
  with a deliberately-corrupted input this mission; `media.py`'s
  functions raise `RuntimeError` on any non-zero return code from `say`/
  `ffmpeg` rather than fabricating a render record, which is
  code-reviewable but not independently proven with a forced-failure
  test here.
- **Channel-selection ambiguity (two channels matching equally well):**
  `channel.py::select_channel()`'s tie-break is "first channel reaching
  the highest score in dict iteration order" -- not independently tested
  for a genuine tie, since the three real configured channel identities
  (AI-tech, US stock market, AI-education) do not naturally tie for any
  real event content encountered during construction.
