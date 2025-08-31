#!/bin/bash

# UatuAudit Dashboard Production Deployment Script

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 UatuAudit Dashboard Production Deployment${NC}"

# Check if dashboard.env exists
if [[ ! -f "dashboard.env" ]]; then
    echo -e "${RED}❌ Error: dashboard.env not found${NC}"
    echo "Please create dashboard.env with your production configuration:"
    echo "cp dashboard.env.example dashboard.env"
    echo "Then edit dashboard.env with your actual values"
    exit 1
fi

# Load environment variables
echo -e "${BLUE}📋 Loading configuration from dashboard.env...${NC}"
source dashboard.env

# Validate required environment variables
required_vars=("APP_SECRET" "GITHUB_CLIENT_ID" "GITHUB_CLIENT_SECRET")
for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]] || [[ "${!var}" == "your_*" ]]; then
        echo -e "${RED}❌ Error: $var is not set or has default value${NC}"
        echo "Please update dashboard.env with your actual values"
        exit 1
    fi
done

# Check if at least one access control method is configured
if [[ -z "${ALLOWED_EMAILS:-}" ]] && [[ -z "${ALLOWED_ORGS:-}" ]]; then
    echo -e "${RED}❌ Error: No access control configured${NC}"
    echo "Please set either ALLOWED_EMAILS or ALLOWED_ORGS in dashboard.env"
    exit 1
fi

echo -e "${GREEN}✅ Configuration validated${NC}"

# Build Docker image if needed
echo -e "${BLUE}🐳 Building Docker image...${NC}"
docker build -t contract-auditor:prod .

# Stop existing dashboard if running
echo -e "${BLUE}🛑 Stopping existing dashboard...${NC}"
docker compose down dashboard 2>/dev/null || true

# Start dashboard
echo -e "${BLUE}🚀 Starting dashboard...${NC}"
docker compose up -d dashboard

# Wait for dashboard to be ready
echo -e "${BLUE}⏳ Waiting for dashboard to be ready...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:${PORT:-8080}/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Dashboard is ready!${NC}"
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo -e "${RED}❌ Dashboard failed to start within 30 seconds${NC}"
        echo "Check logs with: docker compose logs dashboard"
        exit 1
    fi
    echo -n "."
    sleep 1
done

# Show dashboard status
echo -e "\n${BLUE}📊 Dashboard Status:${NC}"
docker compose ps dashboard

# Show access URLs
echo -e "\n${GREEN}🌐 Dashboard Access:${NC}"
echo "Local: http://localhost:${PORT:-8080}"
echo "Health: http://localhost:${PORT:-8080}/health"

# Show logs
echo -e "\n${BLUE}📋 Recent logs:${NC}"
docker compose logs --tail=10 dashboard

echo -e "\n${GREEN}🎉 Dashboard deployment completed!${NC}"
echo ""
echo "Next steps:"
echo "1. Configure reverse proxy (nginx) for production"
echo "2. Set up SSL certificates (Let's Encrypt)"
echo "3. Configure monitoring and alerts"
echo ""
echo "Useful commands:"
echo "  View logs: docker compose logs -f dashboard"
echo "  Stop: docker compose down dashboard"
echo "  Restart: docker compose restart dashboard"
echo "  Update: ./deploy-dashboard.sh"
