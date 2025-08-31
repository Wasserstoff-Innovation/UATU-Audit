#!/bin/bash

# UatuAudit Contract Deployment Script
# Deploys AuditOrders.sol to Base network

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 UatuAudit Contract Deployment${NC}"

# Check if Foundry is installed
if ! command -v forge &> /dev/null; then
    echo -e "${RED}❌ Error: Foundry not found${NC}"
    echo "Please install Foundry first:"
    echo "curl -L https://foundry.paradigm.xyz | bash"
    echo "foundryup"
    exit 1
fi

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please create .env file with your configuration:"
    echo ""
    echo "# Base Network Configuration"
    echo "BASE_RPC_URL=https://mainnet.base.org"
    echo "BASE_PRIVATE_KEY=your_private_key_here"
    echo "BASE_EXPLORER=https://basescan.org"
    echo ""
    echo "# Contract Configuration"
    echo "TREASURY_ADDRESS=your_treasury_address"
    echo "USDC_ADDRESS=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    echo "AUDIT_PRICE=100000000"
    echo ""
    exit 1
fi

# Load environment variables
source .env

# Validate required environment variables
required_vars=("BASE_RPC_URL" "BASE_PRIVATE_KEY" "TREASURY_ADDRESS" "USDC_ADDRESS" "AUDIT_PRICE")
for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo -e "${RED}❌ Error: $var is not set in .env${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ Environment configuration loaded${NC}"

# Check if contracts directory exists
if [[ ! -d "contracts" ]]; then
    echo -e "${RED}❌ Error: contracts directory not found${NC}"
    echo "Please ensure you're in the UatuAudit root directory"
    exit 1
fi

# Check if AuditOrders.sol exists
if [[ ! -f "contracts/AuditOrders.sol" ]]; then
    echo -e "${RED}❌ Error: contracts/AuditOrders.sol not found${NC}"
    echo "Please ensure the contract file exists"
    exit 1
fi

echo -e "${BLUE}📋 Deployment Configuration:${NC}"
echo "• Network: Base Mainnet"
echo "• RPC URL: ${BASE_RPC_URL}"
echo "• Treasury: ${TREASURY_ADDRESS}"
echo "• USDC: ${USDC_ADDRESS}"
echo "• Price: ${AUDIT_PRICE} (${AUDIT_PRICE} wei = $((AUDIT_PRICE / 1000000)) USDC)"
echo "• Explorer: ${BASE_EXPLORER}"

# Confirmation prompt
echo -e "\n${YELLOW}⚠️  WARNING: This will deploy to Base Mainnet!${NC}"
echo -e "${YELLOW}Ensure you have sufficient ETH for gas fees.${NC}"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " -r
if [[ ! "$REPLY" =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${BLUE}Deployment cancelled.${NC}"
    exit 0
fi

echo -e "\n${GREEN}🚀 Starting deployment...${NC}"

# Create deployment directory if it doesn't exist
mkdir -p deployments

# Deploy contract
echo -e "${BLUE}📝 Deploying AuditOrders contract...${NC}"
forge create \
    --rpc-url "${BASE_RPC_URL}" \
    --private-key "${BASE_PRIVATE_KEY}" \
    --etherscan-api-key "${BASE_EXPLORER_API_KEY:-}" \
    --verify \
    contracts/AuditOrders.sol:AuditOrders \
    --constructor-args "${TREASURY_ADDRESS}" "${USDC_ADDRESS}" "${AUDIT_PRICE}"

# Get deployment address
DEPLOYMENT_OUTPUT=$(forge create \
    --rpc-url "${BASE_RPC_URL}" \
    --private-key "${BASE_PRIVATE_KEY}" \
    --json \
    contracts/AuditOrders.sol:AuditOrders \
    --constructor-args "${TREASURY_ADDRESS}" "${USDC_ADDRESS}" "${AUDIT_PRICE}")

CONTRACT_ADDRESS=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.deployedTo')

if [[ "$CONTRACT_ADDRESS" == "null" ]] || [[ -z "$CONTRACT_ADDRESS" ]]; then
    echo -e "${RED}❌ Error: Failed to get contract address${NC}"
    echo "Deployment output:"
    echo "$DEPLOYMENT_OUTPUT"
    exit 1
fi

echo -e "${GREEN}✅ Contract deployed successfully!${NC}"
echo "Contract Address: ${CONTRACT_ADDRESS}"

# Save deployment info
DEPLOYMENT_INFO=$(cat <<EOF
{
    "contract": "AuditOrders",
    "address": "${CONTRACT_ADDRESS}",
    "network": "Base Mainnet",
    "deployed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "constructor_args": {
        "treasury": "${TREASURY_ADDRESS}",
        "usdc": "${USDC_ADDRESS}",
        "price": "${AUDIT_PRICE}"
    },
    "explorer": "${BASE_EXPLORER}/address/${CONTRACT_ADDRESS}",
    "verification": "forge verify-contract ${CONTRACT_ADDRESS} contracts/AuditOrders.sol:AuditOrders --chain-id 8453 --constructor-args $(cast abi-encode "constructor(address,address,uint256)" "${TREASURY_ADDRESS}" "${USDC_ADDRESS}" "${AUDIT_PRICE}")"
}
EOF
)

echo "$DEPLOYMENT_INFO" > "deployments/audit-orders-$(date +%Y%m%d-%H%M%S).json"

echo -e "\n${BLUE}📋 Deployment Summary:${NC}"
echo "• Contract: AuditOrders"
echo "• Address: ${CONTRACT_ADDRESS}"
echo "• Network: Base Mainnet"
echo "• Explorer: ${BASE_EXPLORER}/address/${CONTRACT_ADDRESS}"
echo "• Treasury: ${TREASURY_ADDRESS}"
echo "• USDC: ${USDC_ADDRESS}"
echo "• Price: $((AUDIT_PRICE / 1000000)) USDC"

echo -e "\n${BLUE}🔧 Next Steps:${NC}"
echo "1. Update wallet-demo.html with contract address: ${CONTRACT_ADDRESS}"
echo "2. Test the contract with a small amount first"
echo "3. Verify the contract on BaseScan"
echo "4. Update your backend to listen for OrderPaid events"

echo -e "\n${GREEN}🎉 Deployment completed successfully!${NC}"

# Save contract address to .env for easy access
if ! grep -q "CONTRACT_ADDRESS" .env; then
    echo "" >> .env
    echo "# Deployed Contract" >> .env
    echo "CONTRACT_ADDRESS=${CONTRACT_ADDRESS}" >> .env
    echo -e "${BLUE}✅ Contract address saved to .env${NC}"
fi
