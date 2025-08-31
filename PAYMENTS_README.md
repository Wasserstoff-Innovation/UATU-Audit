# UatuAudit Payment System

## 🎯 **Overview**

The UatuAudit Payment System provides secure, on-chain payments for smart contract audits on the Base network. Built with enterprise-grade security and production-ready features.

## 🏗️ **Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Smart         │    │   Backend       │
│   (Wallet)      │───▶│   Contract      │───▶│   (Listener)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Payment       │    │   OrderPaid     │    │   Audit Queue   │
│   Confirmation  │    │   Event         │    │   Processing    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔒 **Security Features**

### **Smart Contract Security**
- **SafeERC20**: Secure token transfers with proper error handling
- **ReentrancyGuard**: Protection against reentrancy attacks
- **Pausable**: Emergency stop functionality
- **Ownable2Step**: Secure ownership transfer with confirmation
- **Input Validation**: Comprehensive parameter validation
- **Price Limits**: Configurable bounds (1-1000 USDC)

### **Access Control**
- **Owner-only functions**: Price updates, treasury changes, pausing
- **Emergency functions**: Token withdrawal, contract pausing
- **Two-step ownership**: Secure ownership transfer process

## 🚀 **Quick Start**

### **1. Prerequisites**
```bash
# Install Foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Install Node.js dependencies
npm install
```

### **2. Environment Configuration**
```bash
# Copy example environment
cp .env.example .env

# Edit with your configuration
nano .env
```

**Required Environment Variables:**
```bash
# Base Network
BASE_RPC_URL=https://mainnet.base.org
BASE_WS_URL=wss://base-mainnet.g.alchemy.com/v2/xxx
BASE_PRIVATE_KEY=your_deployment_key
BASE_EXPLORER=https://basescan.org
BASE_EXPLORER_API_KEY=your_api_key

# Contract
TREASURY_ADDRESS=0x...  # Your secure treasury
USDC_ADDRESS=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
AUDIT_PRICE=100000000  # 100 USDC (6 decimals)

# Backend
ORCH_URL=https://uatu.example.com
ORCH_TOKEN=your_secure_token
```

### **3. Deploy Smart Contract**
```bash
# Deploy to Base mainnet
./scripts/deploy-v2-contract.sh

# Or deploy to testnet
npm run deploy:testnet
```

### **4. Start On-Chain Listener**
```bash
# Start listener
npm run listener

# Or development mode with auto-restart
npm run listener:dev
```

## 📋 **Smart Contracts**

### **AuditOrdersV2.sol**
Enhanced security contract with OpenZeppelin protections.

**Key Functions:**
- `payAndStart(repo, commit, salt)`: Process payment and emit event
- `getOrderId(payer, repo, commit, salt)`: Get deterministic order ID
- `checkUserStatus(user)`: Check allowance and balance
- `pause()/unpause()`: Emergency stop functionality
- `setPrice(newPrice)`: Update audit price
- `setTreasury(newTreasury)`: Update treasury address

**Events:**
- `OrderPaid`: Emitted when payment is processed
- `PriceChanged`: Emitted when price is updated
- `TreasuryChanged`: Emitted when treasury is updated
- `Paused/Unpaused`: Emitted when contract is paused/unpaused

### **Testing**
```bash
# Run all tests
forge test

# Run specific contract tests
npm run test:contract

# Run with gas reporting
forge test --gas-report
```

## 🔌 **On-Chain Listener**

### **Features**
- **WebSocket Connection**: Real-time event listening
- **Automatic Reconnection**: Exponential backoff on failures
- **Event Processing**: OrderPaid event parsing and forwarding
- **Health Monitoring**: Connection health checks and heartbeat
- **Error Handling**: Comprehensive error handling and logging
- **Production Ready**: Structured logging and monitoring

### **Configuration**
```typescript
const CONFIG = {
    BASE_WS: process.env.BASE_WS!,
    ORDERS_ADDRESS: process.env.ORDERS_ADDRESS!,
    ORCH_URL: process.env.ORCH_URL!,
    ORCH_TOKEN: process.env.ORCH_TOKEN!,
    LOG_LEVEL: process.env.LOG_LEVEL || 'info',
    HEARTBEAT_INTERVAL: 30000, // 30s
    MAX_RECONNECT_ATTEMPTS: 10,
    RECONNECT_DELAY: 5000 // 5s
};
```

### **Event Processing**
```typescript
contract.on("OrderPaid", async (orderId, payer, repo, commit, amount, token, chainId, event) => {
    // Process OrderPaid event
    await forwardToBackend({
        orderId: orderId.toString(),
        payer: payer.toString(),
        repo: repo.toString(),
        commit: commit.toString(),
        amount: amount.toString(),
        token: token.toString(),
        chainId: chainId.toString(),
        blockNumber: event.log.blockNumber,
        transactionHash: event.log.transactionHash,
        timestamp: Date.now()
    });
});
```

## 💳 **Wallet Integration**

### **Demo Page**
Complete working example at `auditor/dashboard/static/examples/wallet-demo.html`

**Features:**
- MetaMask integration
- Base network switching
- USDC approval and payment
- Transaction monitoring
- Error handling
- Professional Uatu styling

### **Integration Steps**
1. **Include ethers.js**: `<script src="https://cdn.jsdelivr.net/npm/ethers@6.13.2/dist/ethers.min.js"></script>`
2. **Update configuration** with your contract address
3. **Connect wallet** and switch to Base network
4. **Approve USDC** spending
5. **Process payment** with `payAndStart()`

## 🔄 **Backend Integration**

### **Required Endpoint**
```http
POST /api/orders/onchain
Authorization: Bearer <ORCH_TOKEN>
Content-Type: application/json

{
    "orderId": "0x...",
    "payer": "0x...",
    "repo": "owner/name",
    "commit": "abcdef...",
    "amount": "100000000",
    "token": "0x...",
    "chainId": "8453",
    "blockNumber": 12345,
    "transactionHash": "0x...",
    "timestamp": 1234567890
}
```

### **Response Handling**
- **200 OK**: Order processed successfully
- **400 Bad Request**: Invalid order data
- **401 Unauthorized**: Invalid authentication token
- **500 Internal Server Error**: Processing failure

## 🎨 **Uatu Brand Integration**

### **Color Palette**
```css
:root {
    /* Uatu Brand Colors */
    --ink: #0b1b2b;      /* Background */
    --slate: #17293c;    /* Cards */
    --edge: #1f3b57;     /* Borders */
    --glow: #f7d046;     /* Accents */
    
    /* Status Colors */
    --ready: #2e7d32;    /* Ready to Go */
    --pass: #0288d1;     /* Passed Audit */
    --warn: #fbc02d;     /* Needs Fixes */
    --risk: #f57c00;     /* Dangerous */
    --crit: #d32f2f;     /* Critical */
    --muted: #6e7781;    /* Neutral/Aux */
    --llm: #7b1fa2;      /* LLM Assisted */
}
```

### **Badge System**
- **Primary badges**: Large, prominent status indicators
- **Secondary badges**: Small pills for additional context
- **Professional styling**: Consistent with Uatu brand language

## 🚀 **Production Deployment**

### **Pre-Launch Checklist**
- [ ] Contract deployed and verified
- [ ] Treasury address secure and tested
- [ ] Listener running and connected
- [ ] Backend integration complete
- [ ] Monitoring and alerting configured
- [ ] Emergency procedures documented
- [ ] Team training completed

### **Launch Steps**
1. **Deploy contract** to Base mainnet
2. **Verify contract** on BaseScan
3. **Start listener** and verify connection
4. **Test payment flow** with small amount
5. **Enable production** payments
6. **Monitor closely** for first 24 hours

### **Post-Launch Monitoring**
- Payment success rate > 95%
- Event processing latency < 30s
- Audit completion success > 90%
- Error rates < 5%
- Gas costs within budget

## 🔧 **Development & Testing**

### **Local Development**
```bash
# Start listener in development mode
npm run listener:dev

# Run contract tests
npm run test:contract

# Build contracts
npm run build:contract
```

### **Testnet Deployment**
```bash
# Deploy to Base Sepolia
npm run deploy:testnet

# Update environment for testnet
BASE_RPC_URL=https://sepolia.base.org
BASE_WS_URL=wss://base-sepolia.g.alchemy.com/v2/xxx
```

### **Contract Verification**
```bash
# Manual verification
forge verify-contract 0x... contracts/AuditOrdersV2.sol:AuditOrdersV2 \
  --chain-id 8453 \
  --etherscan-api-key YOUR_API_KEY \
  --constructor-args $(cast abi-encode "constructor(address,address,uint256)" \
    "TREASURY" "USDC" "100000000")
```

## 📊 **Monitoring & Maintenance**

### **Health Checks**
- Contract operational status
- Listener connection health
- Event processing latency
- Payment success rate
- Audit queue performance

### **Logging**
- Structured JSON logging
- Configurable log levels
- Log rotation and retention
- Centralized logging support

### **Alerting**
- Contract paused notifications
- Listener disconnection alerts
- Payment failure monitoring
- High latency warnings
- Error rate thresholds

## 🚨 **Emergency Procedures**

### **Contract Pause**
```bash
# Pause contract (owner only)
cast send 0x... "pause()" --private-key OWNER_KEY --rpc-url BASE_RPC

# Verify pause
cast call 0x... "paused()" --rpc-url BASE_RPC
```

### **Treasury Update**
```bash
# Update treasury (owner only)
cast send 0x... "setTreasury(address)" NEW_TREASURY --private-key OWNER_KEY --rpc-url BASE_RPC
```

### **Emergency Withdrawal**
```bash
# Withdraw stuck tokens (owner only)
cast send 0x... "emergencyWithdraw(address,uint256)" TOKEN_ADDRESS AMOUNT --private-key OWNER_KEY --rpc-url BASE_RPC
```

## 📚 **Resources & Support**

### **Documentation**
- [Base Network Documentation](https://docs.base.org/)
- [USDC on Base](https://docs.base.org/guides/deploy-smart-contracts)
- [Foundry Book](https://book.getfoundry.sh/)
- [OpenZeppelin Contracts](https://docs.openzeppelin.com/contracts/)

### **Community**
- [Base Discord](https://discord.gg/base)
- [Foundry Discord](https://discord.gg/getfoundry)
- [UatuAudit Issues](https://github.com/your-org/uatu-audit/issues)

### **Support**
For implementation support:
1. Check this documentation
2. Review error logs and monitoring
3. Test with small amounts first
4. Open GitHub issue with details

## 🎉 **What's Next**

### **Immediate**
- Deploy contract to Base mainnet
- Test payment flow end-to-end
- Start on-chain listener
- Monitor and optimize

### **Future Enhancements**
- Stripe integration for fiat payments
- GitHub App for every-commit plans
- Advanced analytics and reporting
- Multi-chain support
- Automated refund processing

---

**Your UatuAudit payment system is production-ready!** 🚀

Start with the smart contract deployment, then integrate the wallet demo, and finally add the backend event listening. The system is designed to be robust, secure, and scalable for production use.

**Questions?** Check the [PRODUCTION_CHECKLIST.md](./PRODUCTION_CHECKLIST.md) for detailed deployment steps! 🦉
