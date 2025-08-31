# Post-Launch Ops One-Pager

## 🚀 What's Live

- **Per-contract audits (matrix)** → artifacts + gates (overall & delta)
- **Portfolio aggregation** → artifacts + gates (overall & delta)
- **Badges & sparklines** in PR comments (contract + portfolio)
- **Baselines versioned** in repo (`baseline/**`)
- **Soft-fail override** via `RISK_SOFT_FAIL=true`

## ⚡ Daily Checks (60s)

```bash
# Portfolio status
jq -r '.summary | "Portfolio: \(.grade) \(.overall) (Δ \(.delta_overall // 0))"' out-portfolio/*/portfolio.json

# Top risky contracts
jq -r '.summary.top_contracts[0:5][] | "- \(.id): \(.overall) \(.grade) (Δ \(.delta))"' out-portfolio/*/portfolio.json

# Any function deltas > 0 in today's runs
jq -r '.by_function | to_entries[] | select(.value.delta>0) | [.key, .value.score, .value.delta] | @tsv' out/*/runs/risk/risk.json 2>/dev/null
```

## 🚨 When a Gate Goes Red (Triage in 5 min)

1. **Open failing job** → `report.html` → **Top Risky Functions** (or portfolio report)
2. **Decide**: **true regression** (fix code) vs **expected change/noise** (re-baseline)
3. **If blocking work and understood** → set repo var `RISK_SOFT_FAIL=true` (temporary), merge fix, then revert

## 🔧 Re-baseline SOP (Maintainers Only)

- **Run audits on `main`**
- **Commit updated** `baseline/*.risk.json` and `baseline/portfolio.*`
- **CI must pass** → merge
- **Never bump baseline from PR branches**

## ⚙️ Threshold Tuning (Documented)

- **Global defaults** in workflow/env or `docs/config.md`:
  - `MAX_OVERALL` (default 30), `MAX_DELTA` (default 5)
- **Per-contract overrides** recommended (map of ids → `{max_overall,max_delta}`)

---

## 📊 Observability & Quality

### KPIs to Track Weekly
- Portfolio overall & Δ (sparkline trend)
- Count of failing contracts per week
- Top 5 riskiest functions (rolling)
- Test pass rate; LLM compile-precheck **rejection rate**
- STRIDE coverage % (functions with ≥1 category flagged)
- Average CI runtime (matrix + aggregate)

### Slack Alert Ideas (Optional)
- On portfolio overall > threshold or Δ > threshold
- On missing artifacts (no `risk.json` in a job)
- On spike in LLM snippet rejections (compile errors)

---

## 🛡️ Reliability & Security

### Image & Supply Chain
- **Pinned digest** for the auditor image (already in workflow)
- **Quarterly image bump** via controlled PR; compare portfolio deltas before merging
- **Optional**: attach SBOM (`syft`) + vuln scan (`grype`) as non-gating artifacts

### Secrets & Safety
- **Only set LLM keys** if you plan to use `--llm on`
- **`RISK_SOFT_FAIL` default `false`**; treat as emergency brake only

---

## 🔍 Common Issues (Fast Fixes)

| Symptom                      | Likely Cause                          | Fast Fix                                                             |
| ---------------------------- | ------------------------------------- | -------------------------------------------------------------------- |
| Portfolio green, one job red | One outlier contract                  | Fix or re-baseline that contract only                                |
| "No risk.json" artifact      | Path or setup glitch in job           | Re-run job; check workflow paths                                     |
| Empty STRIDE/EoP             | Static analysis stubbed or no signals | Verify slither mode/flags; still safe (pipeline degrades gracefully) |
| LLM section says "disabled"  | No provider keys                      | Set API key or keep `--llm off`                                      |
| CI blocks an urgent merge    | Known change raising risk             | Temporarily set `RISK_SOFT_FAIL=true`; follow with re-baseline PR    |

---

## 📅 Cadence & Ownership

### **Daily**
- Glance at PR badges & sparklines
- Skim portfolio summary

### **Weekly**
- Review top risks, deltas, STRIDE coverage
- Adjust thresholds if needed

### **Quarterly**
- Bump image digest
- Refresh docs
- Reconfirm protected baselines

### **Roles**
- **Maintainer**: owns baselines, thresholds, image bumps
- **Service team**: triage red gates, produce fixes, request re-baseline when appropriate
- **Security**: reviews top risks & trends; signs off threshold changes

---

## 🚀 Near-Term Enhancements (Small SOP Slices)

1. **12.1 Weighting modes**: `aggregate --weighting average|median|max|tvl --weights-file tvl.json`
2. **12.2 Percentile gating**: `--portfolio-percentile 90` (gate if current overall > p90 history)
3. **12.3 Deep links**: portfolio rows link to each contract's `report.html` artifact

---

## 📚 Quick Reference

### **Emergency Controls**
```bash
# Soft-fail mode (set in GitHub repo variables)
RISK_SOFT_FAIL=true

# Check portfolio health
jq -r '.summary | "Portfolio: \(.grade) \(.overall) (Δ \(.delta_overall // 0))"' out-portfolio/*/portfolio.json

# Find highest risk contract
jq -r '.by_contract | to_entries[] | [.key, .value.overall, .value.grade] | @tsv' out-portfolio/*/portfolio.json | sort -k2 -nr | head -5
```

### **Documentation**
- **Config**: `docs/config.md`
- **Runbook**: `docs/post-launch-runbook.md`
- **Quick Ref**: `docs/quick-reference.md`
- **Handover**: `docs/production-handover.md`

---

**Status**: 🟢 **LIVE & PRODUCTION-READY**  
**Next Review**: Quarterly  
**Support**: Documentation in `docs/` directory
