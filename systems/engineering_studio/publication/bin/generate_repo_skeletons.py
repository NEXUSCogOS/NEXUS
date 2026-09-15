#!/usr/bin/env python3
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--publication-root",required=True);a=p.parse_args()
root=Path(a.publication_root)
cfg=json.loads((root/"01_REGISTRY/repositories.json").read_text())
for repo in cfg["repositories"]:
    r=root/"02_PUBLIC_REPOS"/repo["name"]
    for d in ["docs","src","tests","experiments","results","reproduction",".github/workflows"]: (r/d).mkdir(parents=True,exist_ok=True)
    (r/"README.md").write_text(f"""# {repo['name']}

> PUBLIC RELEASE SKELETON — no canonical source has been exported.

## Purpose
{repo['purpose']}

## Research question
TBD from validated canonical research scope.

## Architecture
TBD.

## Experimental design
TBD.

## Results
No results are asserted by this skeleton.

## Reproduction
See `reproduction/README.md`.

## Limitations
See `docs/LIMITATIONS.md`.
""")
    (r/"docs/LIMITATIONS.md").write_text("# Limitations\n\nPopulate from validated evidence before release.\n")
    (r/"reproduction/README.md").write_text("# Reproduction\n\nNo release candidate commissioned yet.\n")
    (r/"SECURITY.md").write_text("# Security\n\nEstablish a private vulnerability reporting channel before publication.\n")
    (r/"LICENSE").write_text("LICENSE NOT YET SELECTED — HUMAN DECISION REQUIRED.\n")
print("Generated four public repository skeletons.")
