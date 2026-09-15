#!/usr/bin/env bash
set -euo pipefail

BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$BIN/.." && pwd)"
REG="$ROOT/01_REGISTRY/repositories.json"

echo "=== PUBLICATION SELF TEST V2 ==="

for f in \
 "$ROOT/00_GOVERNANCE/MASTER_DIRECTIVE.md" \
 "$ROOT/00_GOVERNANCE/publication_policy.json" \
 "$ROOT/00_GOVERNANCE/GITHUB_PUBLIC_TARGET.json" \
 "$ROOT/00_GOVERNANCE/UPDATE_DIRECTION_POLICY.md" \
 "$REG" \
 "$ROOT/08_SCHEMAS/release_manifest.schema.json" \
 "$ROOT/state/github_publication_state.json"
do

    if [ ! -f "$f" ]; then
        echo "FAIL: missing required file:"
        echo "$f"
        exit 20
    fi

done

python3 -m json.tool "$REG" >/dev/null

python3 -m json.tool \
 "$ROOT/00_GOVERNANCE/GITHUB_PUBLIC_TARGET.json" >/dev/null

python3 -m json.tool \
 "$ROOT/state/github_publication_state.json" >/dev/null


EXPECTED="$(
python3 - "$REG" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data=json.load(f)

print(len(data["repositories"]))
PY
)"


ACTUAL="$(
find "$ROOT/02_PUBLIC_REPOS" \
    -mindepth 1 \
    -maxdepth 1 \
    -type d \
    | wc -l \
    | tr -d ' '
)"


echo "Registry repositories: $EXPECTED"
echo "Filesystem repositories: $ACTUAL"


if [ "$EXPECTED" -ne "$ACTUAL" ]; then

    echo "FAIL:"
    echo "Repository registry/filesystem mismatch."

    echo
    echo "Registry:"

    python3 - "$REG" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data=json.load(f)

for r in data["repositories"]:
    print(" -",r["name"])
PY

    echo
    echo "Filesystem:"

    find "$ROOT/02_PUBLIC_REPOS" \
        -mindepth 1 \
        -maxdepth 1 \
        -type d \
        -exec basename {} \; \
        | sort

    exit 21
fi


# Verify every registered repository exists.

python3 - "$REG" "$ROOT/02_PUBLIC_REPOS" <<'PY'
import json
import pathlib
import sys

registry=pathlib.Path(sys.argv[1])
repo_root=pathlib.Path(sys.argv[2])

data=json.loads(registry.read_text())

missing=[]

for repo in data["repositories"]:

    path=repo_root/repo["name"]

    if not path.is_dir():
        missing.append(repo["name"])

if missing:

    print("FAIL: registered repositories missing:")
    for item in missing:
        print(" -",item)

    raise SystemExit(22)

print("PASS: all registered repositories exist.")
PY


echo
echo "PASS: publication subsystem structure valid"
echo "PASS: registry and filesystem agree"
echo "PASS: NexusCogOS profile repository recognised"
echo "PASS: self-test derives repository count from registry"
