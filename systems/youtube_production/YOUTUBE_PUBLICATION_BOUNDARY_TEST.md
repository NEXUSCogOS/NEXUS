# YOUTUBE PUBLICATION BOUNDARY TEST
**NEXUS Federation F8 — 2026-08-28 (MANDATORY, mission section 26)**

## What was tested

`test_f8_publication_rejection_mandatory`
(`tests/f8/test_f8_youtube_production_institution.py`). A delegation
requesting exactly what "Publish this video to YouTube" requires --
`authority=EXTERNAL_ACTION` -- attempted against `recipient=
youtube_production`.

## Mechanism

The SAME structural mechanism already used across this federation:
`authority/model.py::exceeds_phase_ceiling()` and
`delegation/schema.py::DelegationProposal._authority_never_exceeds_
phase_ceiling` (a pydantic `model_validator`). Constructing a
`DelegationProposal` with `authority=AuthorityLevel.EXTERNAL_ACTION`
raises `pydantic.ValidationError` before the object can exist at all --
there is no delegation to deliver, so no specialist code ever runs.

## Real result

```
exceeds_phase_ceiling(EXTERNAL_ACTION)          = True
exceeds_phase_ceiling(HIGH_CONSEQUENCE_ACTION)  = True
exceeds_phase_ceiling(GENERATE_INTERNAL)        = False   (this mission's own ceiling)

DelegationProposal(authority=EXTERNAL_ACTION, objective="Publish this video to YouTube", ...)
  -> pydantic.ValidationError: "authority=<AuthorityLevel.EXTERNAL_ACTION: 'EXTERNAL_ACTION'>
     exceeds the phase ceiling (GENERATE_INTERNAL) -- ..."

AUTHORITY_REJECTED = True
```

## Evidence no upload path was ever touched

The test additionally scans every `.py` file in `systems/
youtube_production/` for any reference to `googleapiclient`,
`youtube_uploader`, or `MediaFileUpload` (the real, pre-existing YouTube
Data API v3 client code documented in YOUTUBE_F8_FORENSIC_REPORT.md).
Result: **zero matches**. This package cannot invoke the upload API even
if a rejected proposal had somehow been delivered, because the code to
do so is never imported anywhere in this institution.

## What this proves, and what it does not

- **Proven:** a publication-authority delegation cannot be constructed;
  no upload API is referenced anywhere in this institution's code; every
  real production mission this mission produced terminated at
  `READY_FOR_PUBLICATION_AUTHORIZATION`, never `PUBLISHED`; no video was
  published; no schedule was created; no external state changed; no
  credentials were used for publication (none exist to use, per
  YOUTUBE_F8_FORENSIC_REPORT.md).
- **Not claimed:** that publication is "impossible" in some absolute
  sense -- only that it is `LIVE_EXECUTION`-style
  `BLOCKED_BY_OBSERVED_CONTROLS` (the same calibrated phrasing this
  federation uses for Sentinel's execution-safety guarantees): a
  deliberate, reviewed, future change to `authority/model.py`'s ceiling
  and a real, connected YouTube channel with real credentials would both
  be required, and neither exists nor is granted by this mission.
