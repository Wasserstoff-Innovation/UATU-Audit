# Quick Reference Card

## 🚀 Daily Operations

### Check Portfolio Status
```bash
# Latest portfolio snapshot
jq -r '.summary | "Portfolio: \(.grade) \(.overall) (Δ \(.delta_overall // 0))"' out-portfolio/*/portfolio.json

# Top risky contracts
jq -r '.summary.top_contracts[0:3][] | "- \(.id): \(.overall) \(.grade) (Δ \(.delta))"' out-portfolio/*/portfolio.json
```

### Investigate Contract Issues
```bash
# Find contract with highest risk
jq -r '.by_contract | to_entries[] | [.key, .value.overall, .value.grade] | @tsv' out-portfolio/*/portfolio.json | sort -k2 -nr | head -5

# Check specific contract's risk details
jq '.by_function | to_entries[] | select(.key | contains("ContractName"))' out/*/runs/risk/risk.json
```

### Emergency Controls
```bash
# Soft-fail mode (set in GitHub repo variables)
RISK_SOFT_FAIL=true

# Immediate rollback (re-pin to previous digest)
# Update .github/workflows/audit.yml with previous image digest
```

## 🔍 Troubleshooting

### Gate Failed - What Now?
1. **Check artifacts**: Open `audit-{id}/report.html` → "Top Risky Functions"
2. **Compare baseline**: `jq '.summary.delta_overall' out/*/runs/risk/risk.json`
3. **Classify**: Real issue (fix code) vs noise (re-baseline)

### Portfolio vs Individual Jobs
- **Individual red, portfolio green**: Single outlier within portfolio threshold
- **Both red**: Systemic risk increase requiring investigation
- **Portfolio red, individual green**: Check portfolio aggregation logic

### Missing Artifacts
- **Risk files missing**: Check contract discovery in CI logs
- **Reports missing**: Verify report generation in audit logs
- **Badges missing**: Check badge generation step in CI

## 📊 Data Queries

### Risk Trends
```bash
# Functions getting worse
jq -r '.by_function | to_entries[] | select(.value.delta > 0) | [.key, .value.score, .value.delta] | @tsv' out/*/runs/risk/risk.json

# Grade distribution
jq -r '.summary.buckets | to_entries[] | "\(.key): \(.value)"' out-portfolio/*/portfolio.json
```

### Contract Comparison
```bash
# Compare two contracts
jq -r '.by_contract | to_entries[] | select(.key | contains("evm-") or contains("stellar-")) | [.key, .value.overall, .value.grade, .value.delta] | @tsv' out-portfolio/*/portfolio.json
```

## 🛠️ Maintenance

### Update Baselines (Maintainers Only)
```bash
# Never on PR branches - only on main
git checkout main
# CI will auto-refresh baselines on push
git push
```

### Image Updates
```bash
# Quarterly controlled updates
docker build -t contract-auditor:new .
# Test on feature branch first
# Update digest in workflow if successful
```

### Artifact Cleanup
- **Retention**: 21 days (automatic)
- **Manual cleanup**: Remove old `out/` and `out-portfolio/` directories
- **Baseline backup**: Keep `baseline/` directory in version control

## 🚨 Emergency Procedures

### Pipeline Down
1. Check GitHub Actions status
2. Verify Docker image availability
3. Check baseline file integrity
4. Use soft-fail mode if needed

### False Positive Gates
1. Document the issue in PR
2. Use soft-fail mode temporarily
3. Re-baseline via maintainer PR
4. Investigate root cause

### Data Corruption
1. Check `portfolio.error.json` for validation failures
2. Verify individual contract risk files
3. Re-run failed audit jobs
4. Check CI logs for errors

## 📞 Support

### Documentation
- **Config**: `docs/config.md`
- **Runbook**: `docs/post-launch-runbook.md`
- **This card**: `docs/quick-reference.md`

### CI Workflow
- **File**: `.github/workflows/audit.yml`
- **Jobs**: discover → build → audit (matrix) → aggregate → refresh-baseline

### Key Files
- **Discovery**: `scripts/discover_contracts.py`
- **Portfolio**: `auditor/portfolio/aggregate.py`
- **Badges**: `auditor/badges/svg.py`
- **Trends**: `auditor/trends/sparkline.py`
