# Post-Launch Runbook (Production Operations)

## 🎯 What "Good" Looks Like on Every PR

### Per-Contract Jobs (Matrix) ✅
- **Artifacts**: `report.html`, `report.md`, `runs/risk/risk.json`, `heatmap.csv`
- **Gates**: `overall ≤ MAX_OVERALL` and `delta ≤ MAX_DELTA`
- **PR Comment**: risk **badge** + **sparkline** + top risky functions

### Portfolio Job ✅
- **Artifacts**: `portfolio.report.html`, `portfolio.json`, `portfolio.heatmap.csv`
- **Gates**: portfolio `overall` & `delta_overall`
- **PR Comment**: portfolio **badge** + **sparkline** + ranked contracts

### Quick Spot-Check (Local or CI Shell)
```bash
jq '.summary | {overall, grade, delta_overall, buckets}' out-portfolio/portfolio.json
head -n 3 out-portfolio/portfolio.heatmap.csv
```

## 🚨 Triage Flow When a Gate Goes Red

### 1. Identify Where It Failed
- **Contract job red** → open its `report.html` → "Top Risky Functions"
- **Portfolio job red** → open `portfolio.report.html` → check top contracts and deltas

### 2. Classify Cause
- **Real issue**: failing tests, STRIDE signals, or new Slither findings → fix contract/code
- **Noise/expected change**: intentional risk increase or new checks → re-baseline (see §3)

### 3. Attach Evidence to PR
- Screenshot table rows + link artifact paths
- Record current thresholds and proposed changes (if any)

## 🔧 Baseline Update SOP (Maintainers Only)

**Never change baselines on PR branches.**

### Create Maintainer PR to `main`:
1. Re-run audits on `main` (CI will produce new artifacts)
2. Commit updated `baseline/*.risk.json` and `baseline/portfolio.*`
3. CI must pass → merge → new baseline becomes source of truth

## ⚙️ Threshold Tuning (Safe, Documented)

### Repository-Wide Defaults
- Live in workflow env or `docs/config.md`:
  - `MAX_OVERALL` (default 30), `MAX_DELTA` (default 5)

### Per-Contract Overrides (Recommended)
- Add a tiny map `{ "<contract-id>": { "max_overall": X, "max_delta": Y } }`
- Read it in gating step before evaluations

### Rule of Thumb
- **Green systems with stable code**: **lower** `MAX_OVERALL` (e.g., 20)
- **Active refactors**: **raise** `MAX_DELTA` temporarily (e.g., 8–10), then revert

## 🛠️ Day-2 Maintenance (Keep It Boring)

### Pinned Image
- Keep digest fixed. Bump quarterly via controlled PR:
  - Run matrix + portfolio on feature branch with new digest
  - If results match or improve → update pinned digest on `main`

### Optional SBOM/Security Scan
- Artifact only; don't gate unless desired:
```bash
syft packages dir:. -o spdx-json > sbom.spdx.json
grype dir:. --fail-on high || true
```

### Artifact Retention
- Keep ≥ 14–21 days (already set)

## 🔍 Handy Queries (JQ One-Liners)

### Overall Portfolio Snapshot
```bash
jq -r '.summary | "Portfolio: \(.grade) \(.overall) (Δ \(.delta_overall // 0))"' out-portfolio/portfolio.json
```

### Top 5 Riskiest Functions Across All Contracts
```bash
jq -r '.summary.top_functions[0:5][] | [.contract,.function,.score,.grade] | @tsv' out/*/runs/risk/risk.json 2>/dev/null
```

### Functions with Worsening Deltas
```bash
jq -r '.by_function | to_entries[] | select(.value.delta != null and .value.delta>0) | [.key, .value.score, .value.delta] | @tsv' out/*/runs/risk/risk.json 2>/dev/null
```

## 🚨 Rollback & Resilience

### Soft-Fail Switch (Pre-Wired)
- Set `RISK_SOFT_FAIL=true` in CI env → convert hard gate to warning for that run

### Immediate Rollback
- Re-pin CI to previous image digest; re-run failed workflow

### Partial Outage (Slither/Etherscan)
- Pipeline already degrades gracefully (stub/static)
- Reports remain valid; gates use available signals only

## ❓ Ops FAQs (Short)

### Why did a contract's delta jump but tests all pass?
Static analysis/STRIDE signals changed (new pattern match or dependency update). Verify `runs/static/*` and STRIDE mapping; if expected, re-baseline.

### Why is portfolio green but a contract job is red?
Portfolio averages across contracts; a single outlier can fail its job while portfolio stays within threshold by design.

### Where do the badges/sparklines come from?
Rendered at runtime and embedded as **data URIs** in PR comments; also uploaded as SVG artifacts (`badge-*.svg`, `sparkline-*.svg`).

## 🗺️ Roadmap Seeds (Next Increments with Crisp AC)

### 12.1 Weighting Modes (avg | median | max | TVL)
- **CLI**: `aggregate --weighting <mode>` (+ `--weights-file` for TVL)
- **AC**: portfolio score reflects selected mode; CSV adds `weighting`; report annotates weighting

### 12.2 Percentile Gating
- **CLI**: `--portfolio-percentile 90` → fail if current overall > p90 of history
- **AC**: portfolio history used to compute percentile; gate logic documented and testable with fixtures

### 12.3 Deep Links
- **AC**: portfolio HTML rows link to each contract's `report.html` artifact path; PR comment includes those links

## 🚀 Production Status

**✅ LIVE, PINNED, AND PRODUCTION-READY**

Your portfolio aggregation system is now operating in production with:
- Enterprise-grade portfolio risk management
- CI/CD integration with risk gating
- Multi-contract support with automatic discovery
- Professional reporting with badges, sparklines, and trends
- Baseline tracking for risk evolution over time
- Enhanced data export for BI/analysis tools

**Every PR now shows both individual contract risks AND portfolio-level risk management!** 🎯
