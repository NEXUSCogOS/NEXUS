#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("path");p.add_argument("--output",required=True);a=p.parse_args()
root=Path(a.path)
patterns={
"private_key":re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
"secret_assignment":re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*[\"']?[A-Za-z0-9_\-/.+=]{12,}"),
"aws_key":re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
"github_token":re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
"absolute_user_path":re.compile(r"/Users/[A-Za-z0-9._-]+/")
}
findings=[];skip={".git",".venv","venv","node_modules","__pycache__"}
for f in root.rglob("*"):
    if not f.is_file() or any(x in f.parts for x in skip): continue
    try:
        if f.stat().st_size>5_000_000: continue
        text=f.read_text(errors="ignore")
    except: continue
    for name,rx in patterns.items():
        for m in rx.finditer(text):
            findings.append({"file":str(f.relative_to(root)),"type":name,"sample":m.group(0)[:80]})
res={"pass":not findings,"findings":findings,
"warning":"Heuristic scan only; passing is not proof of publication safety. Git history needs separate review."}
Path(a.output).write_text(json.dumps(res,indent=2)+"\n")
print(json.dumps({"pass":res["pass"],"finding_count":len(findings)},indent=2))
raise SystemExit(0 if res["pass"] else 3)
