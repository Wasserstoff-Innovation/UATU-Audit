# UatuAudit - Multi-Chain Smart Contract Security Auditor

UatuAudit is a **production-grade, portfolio-aware security auditing framework** for smart contracts across multiple blockchain platforms. It combines static analysis, dynamic testing, threat modeling, and **portfolio risk aggregation** to provide comprehensive security assessments of your entire contract portfolio.

## 🚀 **What's New: Portfolio Risk Aggregation**

Every PR now shows both **individual contract risks** AND **portfolio-level risk management** with:
- 🎯 **Risk Badges** - Visual risk indicators in PR comments
- 📈 **Risk Trends** - Sparklines showing risk evolution over time  
- 📊 **Portfolio Aggregation** - Risk roll-up across all contracts
- 🛡️ **CI Gating** - PRs blocked on configurable risk thresholds
- 📋 **Enhanced Reports** - HTML/MD with comprehensive risk analysis
- 📁 **CSV Export** - BI-ready data with contract metadata
- 🔄 **Baseline Tracking** - Risk evolution monitoring vs historical baselines

## Features

- **Multi-Chain Support**: Analyze contracts on EVM-compatible chains (Ethereum, BSC, Polygon) and Stellar/Soroban
- **STRIDE Threat Modeling**: Automated threat categorization using the STRIDE framework (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)
- **Portfolio Risk Management**: Aggregate risk across all contracts with visual dashboards and trend analysis
- **CI/CD Integration**: GitHub Actions with matrix workflows, risk gating, and automatic baseline management
- **Automated Test Generation**: Creates comprehensive test suites including happy path, negative, and stress tests
- **Static Analysis Integration**: Leverages Slither for deep code analysis and vulnerability detection
- **Dynamic Testing**: Executes generated tests using Foundry (EVM) or Cargo (Stellar)
- **Rich Reporting**: Generates detailed HTML and Markdown reports with findings, test results, and recommendations
- **Docker Support**: Fully containerized for consistent execution across environments
- **LLM Augmentation**: Optional AI-powered analysis enhancement (when enabled)

## Installation

### Using Docker (Recommended)

```bash
# Build the Docker image
docker build -t uatu-audit .

# Run the auditor
docker run --rm -v $(pwd)/out:/app/out uatu-audit auditor --help
```

### Local Installation

Requirements:
- Python 3.11+
- Docker (for static analysis tools)
- Foundry (for EVM testing)
- Cargo (for Stellar/Soroban testing)

```bash
# Install Python dependencies
pip install -e .

# Run the auditor
auditor --help
```

## Usage

### Basic Audit Command

```bash
# Audit a local Solidity contract
auditor audit ./path/to/contract.sol

# Audit a deployed contract via Etherscan
auditor audit 0x1234567890abcdef... --kind evm

# Audit a Stellar/Soroban contract
auditor audit ./path/to/rust/project --kind stellar
```

### Portfolio Aggregation

```bash
# Aggregate risk across all contracts
auditor aggregate --inputs "out/*/runs/risk/risk.json" --out out-portfolio

# With baseline comparison and trend analysis
auditor aggregate --inputs "out/*/runs/risk/risk.json" \
  --out out-portfolio --baseline baseline/portfolio.risk.json \
  --trend on --badge on --export csv
```

### Command Options

```bash
auditor audit [OPTIONS] INPUT

Arguments:
  INPUT                     Contract address or path to source files

Options:
  --kind TEXT              Chain type: evm | stellar (default: evm)
  --out TEXT               Output directory (default: out)
  --risk TEXT              Risk scoring: on | off (default: on)
  --risk-baseline TEXT     Path to baseline risk.json for comparison
  --risk-export TEXT       CSV export: csv | none (default: csv)
  --badge TEXT             Risk badge generation: on | off (default: on)
  --trend TEXT             Risk trend analysis: on | off (default: on)
  --trend-n INTEGER        Trend window size (default: 10)
  --llm TEXT               LLM augmentation: on | off (default: off)
  --slither TEXT           Static analysis mode: auto | host | stub (default: auto)
  --eop TEXT               EoP test gating: auto | stride | heuristic | both | off (default: auto)
  --help                   Show this message and exit
```

### Environment Variables

```bash
# For fetching verified contracts from Etherscan
export ETHERSCAN_API_KEY=your_api_key_here
```

## Project Structure

```
UatuAudit/
├── auditor/                 # Main auditor package
│   ├── cli.py              # Command-line interface
│   ├── core.py             # Orchestration logic
│   ├── flows.py            # Contract flow extraction
│   ├── journeys.py         # User journey mapping
│   ├── stride.py           # STRIDE threat modeling
│   ├── models.py           # Data models
│   ├── utils.py            # Utility functions
│   ├── plugins/            # Extensible plugin system
│   ├── report/             # Report generation
│   │   ├── builder.py      # Report builder
│   │   └── templates/      # HTML/Markdown templates
│   ├── runners/            # Test execution engines
│   │   ├── forge_runner.py    # Foundry test runner
│   │   ├── cargo_runner.py    # Cargo test runner
│   │   ├── slither_runner.py  # Slither static analysis
│   │   └── docker_runner.py   # Docker utilities
│   ├── schemas/            # JSON schemas
│   └── testgen/            # Test generation
│       ├── foundry.py      # Foundry test generator
│       └── soroban.py      # Soroban test generator
├── examples/               # Example contracts
│   ├── sample.sol         # Sample EVM contract
│   ├── sensitive.sol      # Security-focused example
│   └── rust-basic/        # Soroban example
├── tools/                  # Tool configurations
│   ├── foundry.toml       # Foundry config
│   ├── echidna.yaml       # Echidna fuzzer config
│   └── mythril.ini        # Mythril config
├── out/                    # Audit outputs (gitignored)
├── docker-compose.yml      # Docker orchestration
├── Dockerfile             # Container definition
└── pyproject.toml         # Python package config
```

## Audit Workflow

1. **Preparation Phase**
   - Source code acquisition (local or Etherscan)
   - Working directory setup
   - Dependency resolution

2. **Exploration Phase**
   - Contract parsing and AST analysis
   - Function flow extraction
   - State variable mapping
   - Event and modifier detection

3. **Journey Mapping**
   - User interaction path generation
   - Critical function identification
   - Access control analysis

4. **Threat Modeling**
   - Static analysis via Slither
   - STRIDE categorization
   - Vulnerability scoring
   - Risk assessment

5. **Test Generation**
   - Happy path tests (normal operations)
   - Negative tests (unauthorized access)
   - Stress tests (edge cases, DoS scenarios)
   - Fuzzing test templates

6. **Test Execution**
   - Automated test running
   - Result collection
   - Coverage analysis

7. **Report Generation**
   - Finding compilation
   - Risk prioritization
   - Remediation recommendations
   - Executive summary

## Output Structure

Each audit creates a timestamped directory containing:

```
out/YYYYMMDD_HHMMSS/
├── flows.json              # Extracted contract flows
├── journeys.json           # User journey mappings
├── threats.json            # STRIDE-categorized threats
├── tests.json              # Generated test metadata
├── report.html             # Interactive HTML report
├── report.md               # Markdown report
├── badge-risk.svg          # Risk badge visualization
├── sparkline-risk.svg      # Risk trend sparkline
├── work/                   # Working directory
│   └── src/               # Contract source files
├── tests/                  # Generated test suites
│   └── evm/               # Platform-specific tests
│       ├── happy_*/       # Happy path tests
│       ├── negative_*/    # Negative tests
│       └── stress_*/      # Stress tests
└── runs/                   # Execution results
    ├── static/            # Static analysis results
    │   ├── slither.json
    │   └── metadata.json
    ├── risk/              # Risk assessment data
    │   ├── risk.json      # Risk scores and grades
    │   ├── heatmap.csv    # Risk heatmap export
    │   └── history.json   # Risk trend history
    └── tests/             # Test execution results
        └── *.json
```

### Portfolio Output

Portfolio aggregation creates:

```
out-portfolio/YYYYMMDD_HHMMSS/
├── portfolio.json           # Portfolio risk summary
├── portfolio.heatmap.csv    # Contract-level risk data
├── portfolio.report.html    # Portfolio HTML report
├── portfolio.report.md      # Portfolio markdown report
├── badge-portfolio.svg      # Portfolio risk badge
├── sparkline-portfolio.svg  # Portfolio trend sparkline
├── portfolio.history.json   # Portfolio risk history
└── portfolio.trend.meta.json # Trend metadata
```

## Test Categories

### Happy Path Tests
Validate normal contract operations with proper inputs and authorized users.

### Negative Tests
Verify security controls by attempting unauthorized operations and invalid inputs.

### Stress Tests
Test contract resilience under extreme conditions, resource exhaustion, and edge cases.

## STRIDE Threat Model

The framework categorizes findings into six threat categories:

- **Spoofing**: Authentication vulnerabilities, identity theft
- **Tampering**: Data modification, state manipulation
- **Repudiation**: Lack of audit trails, transaction deniability
- **Information Disclosure**: Data leaks, privacy violations
- **Denial of Service**: Resource exhaustion, functionality blocking
- **Elevation of Privilege**: Access control bypass, permission escalation

## Development

### Running Tests
```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=auditor tests/
```

### Adding New Analyzers
Create plugins in `auditor/plugins/` following the base analyzer interface.

### Extending Test Generation
Add templates to `auditor/testgen/` for new test patterns.

## Security Considerations

- Always review generated tests before deployment
- Use multiple analysis tools for comprehensive coverage
- Keep tool configurations updated
- Validate findings through manual review
- Consider false positives in automated analysis

## Contributing

Contributions are welcome! Please ensure:
- Code follows existing patterns and conventions
- Tests are included for new features
- Documentation is updated accordingly
- Security best practices are maintained

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Disclaimer

This tool provides automated security analysis but should not replace professional security audits. Always conduct thorough manual reviews and testing before deploying contracts to production networks.

## Documentation

- **Configuration**: `docs/config.md` - Production defaults and settings
- **Post-Launch Runbook**: `docs/post-launch-runbook.md` - Daily operations
- **Quick Reference**: `docs/quick-reference.md` - Common commands and troubleshooting
- **Production Handover**: `docs/production-handover.md` - Handover overview
- **Ops One-Pager**: `docs/ops-one-pager.md` - Internal wiki reference

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Review existing documentation
- Check example contracts for usage patterns
- Consult the production runbook for operational issues

---

*UatuAudit - Watching over your smart contracts*