#!/usr/bin/env python3
"""
Legacy audit import tool for UatuAudit.
Imports existing audit runs into the canonical audits/ directory structure.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

def find_runs(src_glob):
    """Find audit runs in source directories."""
    for p in sorted(Path().glob(src_glob)):
        r = p / "runs" / "risk" / "risk.json"
        if r.exists():
            yield p, r

def copy_run(src_dir, risk_json, dest_root):
    """Copy a single audit run to the canonical location."""
    with risk_json.open() as f:
        risk = json.load(f)
    
    ts = src_dir.name  # assume folder name is the run id
    dest = dest_root / ts
    dest.mkdir(parents=True, exist_ok=True)

    # Copy key artifacts if present
    artifacts = [
        "report.html", 
        "report.pdf", 
        "badge-risk.svg", 
        "sparkline-risk.svg"
    ]
    
    for rel in artifacts:
        f = src_dir / rel
        if f.exists():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest / rel)

    # Always copy risk.json + meta
    out_risk = dest / "runs" / "risk" / "risk.json"
    out_risk.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(risk_json, out_risk)

    # Copy tests metadata if present
    tests_meta = src_dir / "runs" / "tests" / "meta.json"
    if tests_meta.exists():
        out_tests = dest / "runs" / "tests" / "meta.json"
        out_tests.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tests_meta, out_tests)

    # Minimal index row
    summary = risk.get("summary", {})
    return {
        "id": ts,
        "when": datetime.utcnow().isoformat() + "Z",
        "overall": summary.get("overall", 0),
        "grade": summary.get("grade", "Info"),
        "delta": summary.get("delta_overall", 0),
        "kind": risk.get("kind", "unknown"),
        "paths": {
            "html": str((dest / "report.html").resolve()) if (dest / "report.html").exists() else None,
            "pdf": str((dest / "report.pdf").resolve()) if (dest / "report.pdf").exists() else None
        }
    }

def main():
    """Main import function."""
    ap = argparse.ArgumentParser(description="Import legacy audit runs into canonical structure")
    ap.add_argument("--src", default="out/*", help="glob of legacy run dirs (default: out/*)")
    ap.add_argument("--dest", default="audits", help="canonical audits root (default: audits)")
    ap.add_argument("--dry-run", action="store_true", help="show what would be imported without copying")
    args = ap.parse_args()

    dest_root = Path(args.dest)
    if not args.dry_run:
        dest_root.mkdir(parents=True, exist_ok=True)
    
    index_path = dest_root / "index.json"
    index = []
    
    print(f"🔍 Scanning for audit runs in: {args.src}")
    print(f"📁 Destination: {dest_root}")
    print(f"🚀 Mode: {'DRY RUN' if args.dry_run else 'IMPORT'}")
    print()
    
    for src_dir, risk_json in find_runs(args.src):
        print(f"📋 Found: {src_dir.name}")
        if not args.dry_run:
            row = copy_run(src_dir, risk_json, dest_root)
            index.append(row)
            print(f"   ✅ Copied to: {dest_root / src_dir.name}")
        else:
            print(f"   🔍 Would copy to: {dest_root / src_dir.name}")

    if not args.dry_run and index:
        with index_path.open("w") as f:
            json.dump({"runs": index, "imported_at": datetime.utcnow().isoformat() + "Z"}, f, indent=2)
        print(f"\n🎉 Successfully imported {len(index)} runs -> {index_path}")
    elif args.dry_run:
        print(f"\n🔍 Dry run complete - would import {len(list(find_runs(args.src)))} runs")
    else:
        print("\n⚠️  No audit runs found to import")

    return 0

if __name__ == "__main__":
    sys.exit(main())
