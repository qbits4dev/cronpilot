#!/usr/bin/env python3
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lockfile = root / "uv.lock"
out = root / "requirements-uv.txt"

if not lockfile.exists():
    print("uv.lock not found at", lockfile)
    raise SystemExit(1)

# If running under a newer Python, provide overrides for packages
# that are pinned in the lock but are not compatible with the
# current interpreter. Add more entries here if needed.
overrides = {}
if sys.version_info >= (3, 13):
    # blis 1.2.0 does not support Python >=3.13; prefer a 1.3.x release
    overrides["blis"] = "1.3.3"

reqs = []
name = None
version = None
editable = False
with lockfile.open(encoding="utf-8") as fh:
    for line in fh:
        s = line.strip()
        if s.startswith("[[package]]"):
            if name and version and not editable:
                reqs.append((name, version))
            name = None
            version = None
            editable = False
        elif s.startswith("name ="):
            m = re.search(r'"([^"]+)"', s)
            if m:
                name = m.group(1)
        elif s.startswith("version ="):
            m = re.search(r'"([^"]+)"', s)
            if m:
                version = m.group(1)
        elif "editable" in s:
            editable = True

if name and version and not editable:
    reqs.append((name, version))

# Deduplicate: keep the last specified version for any package name
last_versions = {}
for n, v in reqs:
    last_versions[n] = v

out_reqs = []
for n, v in last_versions.items():
    if n in overrides:
        out_reqs.append(f"{n}=={overrides[n]}")
    else:
        out_reqs.append(f"{n}=={v}")

out.write_text("\n".join(out_reqs))
print(f"Wrote {len(out_reqs)} entries to {out}")
