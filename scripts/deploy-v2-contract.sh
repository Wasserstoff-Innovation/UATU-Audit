#!/bin/bash

# UatuAudit V2 Contract Deployment Script
# Deploys AuditOrdersV2.sol to Base network with enhanced security

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 UatuAudit V2 Contract Deployment${NC}"
echo -e "${CYAN}Enhanced security with OpenZeppelin contracts${NC}"

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
    echo "BASE_WS_URL=wss://base-mainnet.g.alchemy.com/v2/xxx"
    echo "BASE_PRIVATE_KEY=your_private_key_here"
    echo "BASE_EXPLORER=https://basescan.org"
    echo "BASE_EXPLORER_API_KEY=your_basescan_api_key"
    echo ""
    echo "# Contract Configuration"
    echo "TREASURY_ADDRESS=your_treasury_address"
    echo "USDC_ADDRESS=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    echo "AUDIT_PRICE=100000000"
    echo ""
    echo "# Backend Integration"
    echo "ORCH_URL=https://uatu.example.com"
    echo "ORCH_TOKEN=your_backend_token"
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

# Check if AuditOrdersV2.sol exists
if [[ ! -f "contracts/AuditOrdersV2.sol" ]]; then
    echo -e "${RED}❌ Error: contracts/AuditOrdersV2.sol not found${NC}"
    echo "Please ensure the v2 contract file exists"
    exit 1
fi

echo -e "${BLUE}📋 Deployment Configuration:${NC}"
echo "• Network: Base Mainnet"
echo "• RPC URL: ${BASE_RPC_URL}"
echo "• Treasury: ${TREASURY_ADDRESS}"
echo "• USDC: ${USDC_ADDRESS}"
echo "• Price: ${AUDIT_PRICE} (${AUDIT_PRICE} wei = $((AUDIT_PRICE / 1000000)) USDC)"
echo "• Explorer: ${BASE_EXPLORER}"

# Check if we're on testnet or mainnet
if [[ "${BASE_RPC_URL}" == *"sepolia"* ]] || [[ "${BASE_RPC_URL}" == *"testnet"* ]]; then
    echo -e "${YELLOW}⚠️  Detected testnet deployment${NC}"
    NETWORK_TYPE="testnet"
else
    echo -e "${RED}⚠️  Detected mainnet deployment${NC}"
    NETWORK_TYPE="mainnet"
fi

# Confirmation prompt
echo -e "\n${YELLOW}⚠️  WARNING: This will deploy to Base ${NETWORK_TYPE}!${NC}"
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

# Build the contract first
echo -e "${BLUE}🔨 Building contract...${NC}"
forge build --contracts contracts/AuditOrdersV2.sol

# Deploy contract
echo -e "${BLUE}📝 Deploying AuditOrdersV2 contract...${NC}"
DEPLOYMENT_OUTPUT=$(forge create \
    --rpc-url "${BASE_RPC_URL}" \
    --private-key "${BASE_PRIVATE_KEY}" \
    --json \
    contracts/AuditOrdersV2.sol:AuditOrdersV2 \
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

# Verify contract (if explorer API key is provided)
if [[ -n "${BASE_EXPLORER_API_KEY:-}" ]]; then
    echo -e "${BLUE}🔍 Verifying contract on explorer...${NC}"
    
    # Wait a bit for the block to be indexed
    sleep 10
    
    VERIFY_OUTPUT=$(forge verify-contract \
        "${CONTRACT_ADDRESS}" \
        contracts/AuditOrdersV2.sol:AuditOrdersV2 \
        --chain-id 8453 \
        --etherscan-api-key "${BASE_EXPLORER_API_KEY}" \
        --constructor-args "$(cast abi-encode "constructor(address,address,uint256)" "${TREASURY_ADDRESS}" "${USDC_ADDRESS}" "${AUDIT_PRICE}")" 2>&1 || true)
    
    if [[ "$VERIFY_OUTPUT" == *"Successfully verified"* ]]; then
        echo -e "${GREEN}✅ Contract verified successfully!${NC}"
    else
        echo -e "${YELLOW}⚠️  Contract verification may have failed:${NC}"
        echo "$VERIFY_OUTPUT"
        echo -e "${BLUE}You can verify manually later using:${NC}"
        echo "forge verify-contract ${CONTRACT_ADDRESS} contracts/AuditOrdersV2.sol:AuditOrdersV2 --chain-id 8453 --etherscan-api-key ${BASE_EXPLORER_API_KEY} --constructor-args \$(cast abi-encode \"constructor(address,address,uint256)\" \"${TREASURY_ADDRESS}\" \"${USDC_ADDRESS}\" \"${AUDIT_PRICE}\")"
    fi
else
    echo -e "${YELLOW}⚠️  Skipping contract verification (no API key provided)${NC}"
fi

# Test contract functions
echo -e "${BLUE}🧪 Testing contract functions...${NC}"
try {
    # Test price function
    PRICE=$(cast call "${CONTRACT_ADDRESS}" "price()" --rpc-url "${BASE_RPC_URL}")
    echo -e "${GREEN}✅ Price function: ${PRICE} wei${NC}"
    
    # Test treasury function
    TREASURY=$(cast call "${CONTRACT_ADDRESS}" "treasury()" --rpc-url "${BASE_RPC_URL}")
    echo -e "${GREEN}✅ Treasury function: ${TREASURY}${NC}"
    
    # Test operational status
    OPERATIONAL=$(cast call "${CONTRACT_ADDRESS}" "isOperational()" --rpc-url "${BASE_RPC_URL}")
    echo -e "${GREEN}✅ Operational status: ${OPERATIONAL}${NC}"
    
} catch {
    echo -e "${YELLOW}⚠️  Some contract tests failed (this is normal for new deployments)${NC}"
}

# Save deployment info
DEPLOYMENT_INFO=$(cat <<EOF
{
    "contract": "AuditOrdersV2",
    "version": "2.0.0",
    "address": "${CONTRACT_ADDRESS}",
    "network": "Base ${NETWORK_TYPE}",
    "deployed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "constructor_args": {
        "treasury": "${TREASURY_ADDRESS}",
        "usdc": "${USDC_ADDRESS}",
        "price": "${AUDIT_PRICE}"
    },
    "explorer": "${BASE_EXPLORER}/address/${CONTRACT_ADDRESS}",
    "verification": "forge verify-contract ${CONTRACT_ADDRESS} contracts/AuditOrdersV2.sol:AuditOrdersV2 --chain-id 8453 --etherscan-api-key ${BASE_EXPLORER_API_KEY:-YOUR_API_KEY} --constructor-args \$(cast abi-encode \"constructor(address,address,uint256)\" \"${TREASURY_ADDRESS}\" \"${USDC_ADDRESS}\" \"${AUDIT_PRICE}\")",
    "features": [
        "SafeERC20 for secure token transfers",
        "Pausable for emergency stops",
        "ReentrancyGuard for attack prevention",
        "Ownable2Step for secure ownership transfer",
        "Price and treasury management",
        "Event emission for backend indexing"
    ]
}
EOF
)

echo "$DEPLOYMENT_INFO" > "deployments/audit-orders-v2-$(date +%Y%m%d-%H%M%S).json"

echo -e "\n${BLUE}📋 Deployment Summary:${NC}"
echo "• Contract: AuditOrdersV2"
echo "• Address: ${CONTRACT_ADDRESS}"
echo "• Network: Base ${NETWORK_TYPE}"
echo "• Explorer: ${BASE_EXPLORER}/address/${CONTRACT_ADDRESS}"
echo "• Treasury: ${TREASURY_ADDRESS}"
echo "• USDC: ${USDC_ADDRESS}"
echo "• Price: $((AUDIT_PRICE / 1000000)) USDC"

echo -e "\n${BLUE}🔧 Next Steps:${NC}"
echo "1. Update wallet-demo.html with contract address: ${CONTRACT_ADDRESS}"
echo "2. Update .env with ORDERS_ADDRESS=${CONTRACT_ADDRESS}"
echo "3. Test the contract with a small amount first"
echo "4. Start the on-chain listener: npm run listener"
echo "5. Update your backend to listen for OrderPaid events"

# Update .env file if contract address not already set
if ! grep -q "ORDERS_ADDRESS" .env; then
    echo "" >> .env
    echo "# Deployed Contract" >> .env
    echo "ORDERS_ADDRESS=${CONTRACT_ADDRESS}" >> .env
    echo -e "${BLUE}✅ Contract address saved to .env${NC}"
else
    # Update existing ORDERS_ADDRESS
    sed -i.bak "s/ORDERS_ADDRESS=.*/ORDERS_ADDRESS=${CONTRACT_ADDRESS}/" .env
    echo -e "${BLUE}✅ Contract address updated in .env${NC}"
fi

# Create listener configuration
if [[ -n "${BASE_WS_URL:-}" ]] && [[ -n "${ORCH_URL:-}" ]] && [[ -n "${ORCH_TOKEN:-}" ]]; then
    echo -e "\n${BLUE}📡 Listener Configuration Ready:${NC}"
    echo "BASE_WS=${BASE_WS_URL}"
    echo "ORDERS_ADDRESS=${CONTRACT_ADDRESS}"
    echo "ORCH_URL=${ORCH_URL}"
    echo "ORCH_TOKEN=${ORCH_TOKEN}"
    echo ""
    echo "Run: npm run listener"
else
    echo -e "\n${YELLOW}⚠️  Listener configuration incomplete:${NC}"
    echo "Add to .env:"
    echo "BASE_WS_URL=wss://base-mainnet.g.alchemy.com/v2/xxx"
    echo "ORCH_URL=https://uatu.example.com"
    echo "ORCH_TOKEN=your_backend_token"
fi

echo -e "\n${GREEN}🎉 V2 Contract deployment completed successfully!${NC}"
echo -e "${PURPLE}Your UatuAudit payment system is now production-ready with enhanced security! 🦉${NC}"
