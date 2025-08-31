# Risk Heatmap CSV Format

The contract auditor exports risk data to `runs/risk/heatmap.csv` for downstream analysis in spreadsheets, BI tools, or PR comments.

## File Location
```
out/<timestamp>/runs/risk/heatmap.csv
```

## Columns

| Column | Type | Description |
|--------|------|-------------|
| `contract` | string | Contract name (e.g., "Sample") |
| `function` | string | Function name (e.g., "ping") |
| `score` | float | Risk score (0.0-100.0) |
| `grade` | string | Risk grade (Info, Low, Medium, High, Critical) |
| `delta` | float | Score change vs baseline (+/-) |
| `stride_cats` | string | Comma-separated STRIDE categories |

## Example Data
```csv
contract,function,score,grade,delta,stride_cats
Sample,ping,0.0,Info,0.0,
Sample,getCount,0.0,Info,0.0,
Sample,getUserCount,0.0,Info,0.0,
Sample,reset,0.0,Info,0.0,
Sample,batchPing,0.0,Info,0.0,
```

## Usage Notes

- **Baseline comparison**: When `--risk-baseline` is provided, `delta` shows score changes
- **STRIDE categories**: Empty if no threats detected, otherwise comma-separated list
- **Grades**: Info (0-10), Low (11-25), Medium (26-50), High (51-75), Critical (76-100)
- **Scores**: Higher values indicate higher risk

## Integration Examples

### Google Sheets
```bash
# Import directly into Google Sheets
# File > Import > Upload > Select CSV file
```

### GitHub PR Comments
```bash
# Use in PR comments for risk summaries
echo "Risk Profile: $(head -n 5 runs/risk/heatmap.csv | tail -n +2 | wc -l) functions analyzed"
```

### BI Tools
```bash
# Power BI, Tableau, etc. can directly read this format
# Use as data source for risk dashboards
```
