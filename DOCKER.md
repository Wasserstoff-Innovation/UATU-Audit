# UatuAudit Docker Setup Guide

## Quick Start

### 1. Build the Docker Image

```bash
docker build -t contract-auditor:prod .
```

### 2. Run a Simple Audit

```bash
# Audit a local Solidity file
docker run --rm -v $(pwd):/work -w /work contract-auditor:prod \
  audit examples/sample.sol --kind evm --out /work/out/audit_results

# Audit from Etherscan (requires ETHERSCAN_API_KEY)
docker run --rm -e ETHERSCAN_API_KEY=your_key contract-auditor:prod \
  audit 0x1234... --kind evm --out /tmp/audit
```

### 3. Run the Dashboard

```bash
# Start the dashboard on port 8080
docker run --rm --entrypoint python -p 8080:8080 \
  -v $(pwd):/work -w /work \
  contract-auditor:prod -m auditor.dashboard.server
```

## Docker Compose Setup

### 1. Configuration

Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

### 2. Start All Services

```bash
# Start MongoDB, Dashboard, and Auditor services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### 3. Run Audits with Docker Compose

```bash
# Run an audit using the auditor service
docker-compose run --rm auditor audit examples/sample.sol --kind evm

# Run with LLM features enabled
docker-compose run --rm auditor audit examples/sample.sol \
  --kind evm --llm on --llm-provider openai
```

## Service Endpoints

- **Dashboard**: http://localhost:8081
- **MongoDB**: mongodb://localhost:27017
- **Health Check**: http://localhost:8081/health

## Volume Mounts

The Docker setup uses these volume mounts:

- `./audits`: Audit outputs
- `./out`: Additional outputs
- `./examples`: Example contracts
- `./.uatu_audit`: User workspaces and configurations

## Environment Variables

### Required API Keys

- `OPENAI_API_KEY`: For LLM-powered analysis
- `ANTHROPIC_API_KEY`: For Claude models (optional)
- `GITHUB_TOKEN`: For repository access
- `ETHERSCAN_API_KEY`: For fetching verified contracts

### GitHub OAuth (Dashboard)

- `GITHUB_CLIENT_ID`: OAuth app client ID
- `GITHUB_CLIENT_SECRET`: OAuth app secret
- `GITHUB_WEBHOOK_SECRET`: Webhook validation

### Database

- `MONGODB_URL`: MongoDB connection string
- `DATABASE_URL`: SQLite alternative

## Advanced Usage

### Custom Network

The services use a bridge network `uatu-network` for inter-service communication.

### Persistent Data

MongoDB data is persisted in Docker volumes:
- `mongodb_data`: Database files
- `mongodb_config`: Configuration

### Running Tests

```bash
# Run test suite in Docker
docker run --rm --entrypoint pytest contract-auditor:prod

# Run specific test
docker run --rm --entrypoint pytest contract-auditor:prod tests/test_core.py
```

### Building for Different Architectures

```bash
# Build for ARM64 (M1/M2 Macs)
docker buildx build --platform linux/arm64 -t contract-auditor:prod .

# Build for AMD64 (Intel/AMD)
docker buildx build --platform linux/amd64 -t contract-auditor:prod .
```

## Troubleshooting

### Port Already in Use

If port 8080/8081 is already in use:

```bash
# Change the port in docker-compose.yml or use:
docker run --rm -p 8085:8080 ... # Use port 8085 instead
```

### Permission Issues

If you encounter permission issues with volumes:

```bash
# Set proper permissions
chmod -R 755 audits/ out/ examples/
```

### MongoDB Connection Issues

Ensure MongoDB is running and accessible:

```bash
# Check MongoDB status
docker-compose ps mongodb

# View MongoDB logs
docker-compose logs mongodb
```

### Memory Issues

For large audits, increase Docker memory:

1. Docker Desktop → Preferences → Resources
2. Increase Memory to at least 4GB
3. Apply & Restart

## Production Deployment

For production deployment:

1. Use proper secrets management (not .env files)
2. Enable HTTPS with proper certificates
3. Use managed MongoDB (Atlas, AWS DocumentDB)
4. Set `DEBUG=false` and `ENVIRONMENT=production`
5. Configure proper backup strategies
6. Set up monitoring and alerting

## Support

For issues or questions:
- GitHub Issues: [Report bugs or request features]
- Documentation: Check `/docs` folder
- Dashboard: Access at http://localhost:8081 when running