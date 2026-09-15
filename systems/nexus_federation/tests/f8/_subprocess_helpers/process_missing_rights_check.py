#!/usr/bin/env python3
"""Mission section 28 negative control, run as its own fresh process (see
process_unsupported_claim_check.py's docstring for why: avoiding a
same-process bare-module-name collision with another institution's own
`schema.py`/`rights.py`-shaped modules).

An asset whose rights were never established (rights_status=UNKNOWN) must
be excluded from the usable set, never silently treated as usable.
"""

import json
import os
import sys
from pathlib import Path

YOUTUBE_ROOT = str(Path(__file__).resolve().parents[4] / "youtube_production")
if YOUTUBE_ROOT not in sys.path:
    sys.path.insert(0, YOUTUBE_ROOT)

from rights import make_generated_asset_rights, make_unknown_rights, enforce_rights


def run():
    unknown = make_unknown_rights("stock-footage-asset-1", source="third_party_stock_library")
    generated = make_generated_asset_rights("voice-asset-1", "macos_say", "narration text")

    usable, blocked = enforce_rights([unknown, generated])

    result = {
        "pid": os.getpid(),
        "usable_ids": [r.asset_id for r in usable],
        "blocked_ids": [r.asset_id for r in blocked],
        "unknown_usable_flag": unknown.usable,
        "unknown_rights_status": unknown.rights_status,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
