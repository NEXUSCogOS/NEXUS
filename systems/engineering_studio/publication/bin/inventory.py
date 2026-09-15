#!/usr/bin/env python3
import argparse,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
p=argparse.ArgumentParser()
p.add_argument("--nexus-root",required=True);p.add_argument("--engineering-studio-root",required=True);p.add_argument("--output",required=True)
a=p.parse_args()
def cmd(x):
    try:return subprocess.check_output(x,text=True,stderr=subprocess.DEVNULL).strip()
    except:return None
out={"created_at":datetime.now(timezone.utc).isoformat(),
"nexus_root":str(Path(a.nexus_root).resolve()),
"engineering_studio_root":str(Path(a.engineering_studio_root).resolve()),
"git_toplevel":cmd(["git","-C",a.engineering_studio_root,"rev-parse","--show-toplevel"]),
"git_head":cmd(["git","-C",a.engineering_studio_root,"rev-parse","HEAD"]),
"note":"Descriptive inventory only; no artifact is classified publishable by this report."}
Path(a.output).write_text(json.dumps(out,indent=2)+"\n")
