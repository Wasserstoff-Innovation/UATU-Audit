#!/usr/bin/env python3
import os, json, sys
from pathlib import Path

root = Path(os.getenv("GITHUB_WORKSPACE", "."))

def files(glob):
    return [str(p) for p in root.glob(glob) if p.is_file()]

items = []

for p in files("contracts/evm/**/*.sol"):
    stem = Path(p).stem
    items.append({"id": f"evm-{stem}", "kind": "evm", "path": p})

for p in files("contracts/stellar/**/*.rs"):
    stem = Path(p).stem
    items.append({"id": f"stellar-{stem}", "kind": "stellar", "path": p})

print(json.dumps({"items": items}, indent=2))
