# UatuAudit - Multi-Chain Smart Contract Security Auditor

UatuAudit is a comprehensive, STRIDE-driven security auditing framework for smart contracts across multiple blockchain platforms. It combines static analysis, dynamic testing, and threat modeling to provide thorough security assessments of blockchain applications.

## Features

- **Multi-Chain Support**: Analyze contracts on EVM-compatible chains (Ethereum, BSC, Polygon) and Stellar/Soroban
- **STRIDE Threat Modeling**: Automated threat categorization using the STRIDE framework (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)
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

### Command Options

```bash
auditor audit [OPTIONS] INPUT

Arguments:
  INPUT                     Contract address or path to source files

Options:
  --kind TEXT              Chain type: evm | stellar (default: evm)
  --out TEXT               Output directory (default: out)
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
    └── tests/             # Test execution results
        └── *.json
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

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Review existing documentation
- Check example contracts for usage patterns

---

*UatuAudit - Watching over your smart contracts*