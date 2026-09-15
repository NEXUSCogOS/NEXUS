from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()


def main():

    if len(sys.argv)!=2:
        raise SystemExit(
            "usage: seal_bundle.py BUNDLE"
        )

    root=Path(sys.argv[1])

    if not root.is_dir():
        raise SystemExit("bundle missing")

    files=[]

    for p in sorted(root.rglob("*")):

        if not p.is_file():
            continue

        if p.name in {
            "SHA256SUMS.json",
            "SEAL.json"
        }:
            continue

        files.append({
            "path":str(p.relative_to(root)),
            "sha256":sha(p),
            "size_bytes":p.stat().st_size
        })

    (root/"SHA256SUMS.json").write_text(
        json.dumps(files,indent=2)+"\n"
    )

    seal={
        "sealed_at":
            datetime.now(timezone.utc).isoformat(),

        "file_count":len(files),

        "manifest_sha256":
            sha(root/"SHA256SUMS.json"),

        "sealed":True
    }

    (root/"SEAL.json").write_text(
        json.dumps(seal,indent=2)+"\n"
    )

    print(json.dumps(seal,indent=2))


if __name__=="__main__":
    main()
