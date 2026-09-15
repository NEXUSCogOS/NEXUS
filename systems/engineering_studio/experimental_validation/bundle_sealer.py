from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h=hashlib.sha256()

    with path.open("rb") as fh:
        for block in iter(
            lambda:fh.read(1024*1024),
            b""
        ):
            h.update(block)

    return h.hexdigest()


def seal_bundle(
    experiment_id: str,
    source_dir: Path,
    output_manifest: Path,
) -> dict:

    source_dir=Path(source_dir)

    if not source_dir.is_dir():
        raise FileNotFoundError(source_dir)

    files=[]

    for path in sorted(
        p for p in source_dir.rglob("*")
        if p.is_file()
    ):

        files.append({
            "relative_path":
                str(path.relative_to(source_dir)),
            "size_bytes":
                path.stat().st_size,
            "sha256":
                sha256(path)
        })

    if not files:
        raise ValueError(
            "Cannot seal an empty evidence bundle"
        )

    manifest={
        "experiment_id":experiment_id,
        "sealed_at":
            datetime.now(timezone.utc).isoformat(),
        "source_dir":str(source_dir.resolve()),
        "file_count":len(files),
        "files":files
    }

    output_manifest.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_manifest.write_text(
        json.dumps(manifest,indent=2)+"\n"
    )

    manifest["manifest_sha256"] = \
        sha256(output_manifest)

    return manifest


def verify_bundle(
    manifest_path: Path,
    source_dir: Path,
) -> dict:

    manifest=json.loads(
        Path(manifest_path).read_text()
    )

    source_dir=Path(source_dir)

    failures=[]

    for item in manifest["files"]:

        path=(
            source_dir /
            item["relative_path"]
        )

        if not path.is_file():

            failures.append({
                "path":str(path),
                "reason":"MISSING"
            })

            continue

        actual=sha256(path)

        if actual != item["sha256"]:

            failures.append({
                "path":str(path),
                "reason":"HASH_MISMATCH"
            })

    return {
        "valid":not failures,
        "failure_count":len(failures),
        "failures":failures
    }
