# SOURCE HIERARCHY
**NEXUS Federation F3 — 2026-08-27**

## The taxonomy

```
PRIMARY / AUTHORITATIVE
PEER_REVIEWED
ACADEMIC_PREPRINT
GOVERNMENT / INSTITUTIONAL
TECHNICAL DOCUMENTATION
INDUSTRY RESEARCH
NEWS
SECONDARY WEB
UNKNOWN
```

## Real classification of the current corpus

**All 93 real sources classify as `TECHNICAL DOCUMENTATION`** — see
`LIBRARIAN_CORPUS_AUDIT.md` section 3 for the full accounting. Zero
sources fall into any other tier. No source is upgraded based on
appearance: a well-formatted Markdown file with a table of contents is
still what it actually is (a user manual), never inferred to be
`PRIMARY`/`PEER_REVIEWED` from formatting alone.

## Classification mechanism

There is currently NO automated classifier — this taxonomy is applied by
direct human/audit inspection of the real ingested rows (title, url,
content sample), documented in `LIBRARIAN_CORPUS_AUDIT.md`. Building an
automated classifier is explicitly `NOT_COMMISSIONED`
(`LIBRARIAN_LIMITATIONS.md`): the current corpus has no examples of any
tier other than `TECHNICAL DOCUMENTATION` to validate a classifier
against, so building one now would be speculative, untested code — the
donor's own anti-pattern this recovery explicitly avoids repeating.
