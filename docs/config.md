# Contract Auditor Configuration

## Production Defaults

### Risk Gates
- **MAX_OVERALL**: 30 (maximum acceptable risk score)
- **MAX_DELTA**: 5 (maximum acceptable risk increase vs baseline)
- **PORTFOLIO_MAX_OVERALL**: 30 (portfolio-level risk threshold)
- **PORTFOLIO_MAX_DELTA**: 5 (portfolio-level delta threshold)

### Trend Configuration
- **--trend-n**: 10 (default trend window size)
- **--trend**: on (default trend generation)

### Analysis Modes
- **--eop**: auto (automatic elevation of privilege analysis)
- **--slither**: auto (automatic static analysis)
- **--llm**: off (LLM analysis disabled by default)
- **--risk**: on (risk scoring enabled)
- **--badge**: on (risk badges generated)
- **--export**: csv (CSV export enabled)

### CI/CD Settings
- **Concurrency**: `${{ github.workflow }}-${{ github.ref }}`
- **Fail Fast**: false (audit all contracts independently)
- **Artifact Retention**: 21 days
- **Baseline Protection**: Required CI checks for baseline updates

### Docker Image
- **Production Tag**: `contract-auditor:prod`
- **Digest**: `sha256:dbc9b6514d2299d46194be3a8a797ffac16f4ee548317046f1488cce8d2fba6c`
- **Base**: `python:3.11-slim`

## Environment Variables

### Required (if LLM enabled)
- `OPENAI_API_KEY`: OpenAI API key for LLM analysis
- `ANTHROPIC_API_KEY`: Anthropic API key for LLM analysis

### Optional
- `SLACK_WEBHOOK_URL`: Slack webhook for portfolio notifications
- `RISK_SOFT_FAIL`: Set to "true" for warning-only mode

## Contract Discovery

### EVM Contracts
- **Location**: `contracts/evm/**/*.sol`
- **ID Format**: `evm-{filename_stem}`

### Stellar Contracts
- **Location**: `contracts/stellar/**/*.rs`
- **ID Format**: `stellar-{filename_stem}`

## Baseline Management

### Per-Contract Baselines
- **Location**: `baseline/{contract_id}.risk.json`
- **Update**: Automatic on main branch pushes
- **Protection**: CI required for baseline changes

### Portfolio Baselines
- **Location**: `baseline/portfolio.risk.json`
- **History**: `baseline/portfolio.history.json`
- **Update**: Automatic on main branch pushes

## Output Structure

### Individual Audits
```
out/{timestamp}/
├── report.html          # HTML risk report
├── report.md            # Markdown risk report
├── runs/risk/
│   ├── risk.json       # Risk assessment data
│   ├── heatmap.csv     # Risk heatmap export
│   └── history.json    # Local trend history
├── badge-risk.svg      # Risk badge
└── sparkline-risk.svg  # Risk trend
```

### Portfolio Aggregation
```
out-portfolio/{timestamp}/
├── portfolio.json           # Portfolio summary
├── portfolio.heatmap.csv    # Contract-level data
├── portfolio.report.html    # Portfolio HTML report
├── portfolio.report.md      # Portfolio markdown report
├── badge-portfolio.svg      # Portfolio risk badge
├── sparkline-portfolio.svg  # Portfolio trend
├── portfolio.history.json   # Portfolio history
└── portfolio.trend.meta.json # Trend metadata
```

## Risk Scoring

### Grade Thresholds
- **Critical**: ≥ 90
- **High**: 70-89
- **Medium**: 50-69
- **Low**: 20-49
- **Info**: 0-19

### Color Scheme
- **Critical**: #d32f2f (red)
- **High**: #f57c00 (orange)
- **Medium**: #fbc02d (yellow)
- **Low**: #0288d1 (blue)
- **Info**: #2e7d32 (green)

## Troubleshooting

### Common Issues
1. **Risk gate tripped**: Check individual contract reports for top risky functions
2. **Missing risk files**: Verify contract discovery and matrix generation
3. **Baseline conflicts**: Use maintainer PRs to update baselines

### Rollback Procedures
1. **Soft fail**: Set `RISK_SOFT_FAIL=true` for warning-only mode
2. **Image rollback**: Re-pin to previous digest in workflow
3. **Baseline reset**: Re-run CI on main branch to refresh baselines
