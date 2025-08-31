# UatuAudit Production Deployment Checklist

## 🎯 **Pre-Launch Security & Configuration**

### **Smart Contract Security** ✅
- [ ] **Contract owner** on hardware wallet (Ledger/Trezor)
- [ ] **Treasury address** verified and secure
- [ ] **Pause function** tested and working
- [ ] **Price limits** configured (1-1000 USDC)
- [ ] **Emergency withdrawal** functions tested
- [ ] **Contract verified** on BaseScan
- [ ] **OpenZeppelin contracts** imported and tested

### **Network Configuration** ✅
- [ ] **Base mainnet** RPC endpoint configured
- [ ] **WebSocket endpoint** for event listening
- [ ] **USDC address** verified (Base mainnet: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
- [ ] **Gas estimation** tested and configured
- [ ] **Block explorer** API key configured

### **Environment Variables** ✅
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
ORDERS_ADDRESS=0x...    # Deployed contract

# Backend
ORCH_URL=https://uatu.example.com
ORCH_TOKEN=your_secure_token
```

## 🔒 **Security Hardening**

### **Access Control**
- [ ] **Contract ownership** transferred to hardware wallet
- [ ] **Treasury address** verified and secure
- [ ] **Admin functions** restricted to owner only
- [ ] **Emergency pause** tested and accessible

### **Input Validation**
- [ ] **Repository format** validation (owner/name)
- [ ] **Commit SHA** validation (40+ characters)
- [ ] **Salt validation** (non-zero bytes32)
- [ ] **Price bounds** enforced (1-1000 USDC)

### **Attack Prevention**
- [ ] **Reentrancy protection** enabled
- [ ] **SafeERC20** for token transfers
- [ ] **Pausable** for emergency stops
- [ ] **Ownable2Step** for secure ownership

## 🧪 **Testing & Validation**

### **Contract Testing**
```bash
# Run Foundry tests
forge test --match-contract AuditOrdersV2

# Expected results:
# ✓ Basic functionality (payAndStart, getOrderId)
# ✓ Input validation (empty repo, commit, salt)
# ✓ Pause functionality (pause/unpause)
# ✓ Admin functions (setPrice, setTreasury)
# ✓ Emergency functions (withdraw, pause)
# ✓ Reentrancy protection
```

### **Integration Testing**
- [ ] **Wallet connection** (MetaMask, WalletConnect)
- [ ] **Network switching** (Base mainnet)
- [ ] **USDC approval** and payment flow
- [ ] **Event emission** and indexing
- [ ] **Backend integration** (order processing)

### **Payment Flow Testing**
- [ ] **Small test payment** (1-5 USDC)
- [ ] **Event processing** by listener
- [ ] **Backend order creation**
- [ ] **Audit job queuing**
- [ ] **Error handling** (insufficient balance, etc.)

## 🚀 **Deployment Steps**

### **1. Deploy Smart Contract**
```bash
# Make script executable
chmod +x scripts/deploy-v2-contract.sh

# Deploy to Base mainnet
./scripts/deploy-v2-contract.sh
```

### **2. Verify Contract**
```bash
# Manual verification if auto-verify fails
forge verify-contract 0x... contracts/AuditOrdersV2.sol:AuditOrdersV2 \
  --chain-id 8453 \
  --etherscan-api-key YOUR_API_KEY \
  --constructor-args $(cast abi-encode "constructor(address,address,uint256)" \
    "TREASURY" "USDC" "100000000")
```

### **3. Update Configuration**
- [ ] **Wallet demo** with contract address
- [ ] **Environment variables** updated
- [ ] **Backend configuration** updated
- [ ] **Listener configuration** ready

### **4. Start On-Chain Listener**
```bash
# Install dependencies
npm install ethers@6.13.2 node-fetch dotenv

# Start listener
npm run listener
# or
npx ts-node scripts/onchain-listener.ts
```

## 📡 **Backend Integration**

### **API Endpoints**
```python
# Required endpoint for listener
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

### **Order Processing**
- [ ] **Order validation** (repo exists, commit valid)
- [ ] **Payment verification** (amount matches price)
- [ ] **Audit job creation** and queuing
- [ ] **Status tracking** (pending → processing → complete)
- [ ] **Error handling** and retry logic

### **Database Schema**
```sql
-- Orders table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(66) UNIQUE NOT NULL,
    payer VARCHAR(42) NOT NULL,
    repo VARCHAR(255) NOT NULL,
    commit VARCHAR(40) NOT NULL,
    amount BIGINT NOT NULL,
    token VARCHAR(42) NOT NULL,
    chain_id INTEGER NOT NULL,
    block_number BIGINT NOT NULL,
    tx_hash VARCHAR(66) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Audits table
CREATE TABLE audits (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    run_ts VARCHAR(20),
    status VARCHAR(20) DEFAULT 'queued',
    overall_score DECIMAL(5,2),
    grade VARCHAR(20),
    delta_overall DECIMAL(5,2),
    artifacts_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 🔄 **GitHub App Integration**

### **App Configuration**
- [ ] **Repository permissions**: Contents (R), PRs (R/W), Checks (R/W)
- [ ] **Webhook events**: `push`, `pull_request`, `check_suite`
- [ ] **Installation**: Users install on repositories
- [ ] **Branch selection**: Protected branches only

### **Every-Commit Plan**
- [ ] **Webhook handler** for push events
- [ ] **Order creation** for each commit
- [ ] **Payment processing** (fiat or crypto)
- [ ] **Audit queuing** and execution
- [ ] **Check posting** (`uatu/audit`)
- [ ] **Branch protection** requiring check success

### **Idempotency**
- [ ] **Unique keys**: `repo + commit + planId`
- [ ] **Duplicate prevention** in database
- [ ] **Retry handling** for webhook failures
- [ ] **Order deduplication** logic

## 📊 **Monitoring & Alerting**

### **Health Checks**
- [ ] **Contract operational** status monitoring
- [ ] **Listener connection** health
- [ ] **Event processing** latency
- [ ] **Payment success** rate
- [ ] **Audit queue** performance

### **Alerting**
- [ ] **Contract paused** notifications
- [ ] **Listener disconnection** alerts
- [ ] **Payment failures** monitoring
- [ ] **High latency** warnings
- [ ] **Error rate** thresholds

### **Logging**
- [ ] **Structured logging** (JSON format)
- [ ] **Log levels** (DEBUG, INFO, WARN, ERROR)
- **Log rotation** and retention
- [ ] **Centralized logging** (ELK stack, etc.)

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

### **Price Update**
```bash
# Update price (owner only)
cast send 0x... "setPrice(uint256)" NEW_PRICE --private-key OWNER_KEY --rpc-url BASE_RPC
```

### **Emergency Withdrawal**
```bash
# Withdraw stuck tokens (owner only)
cast send 0x... "emergencyWithdraw(address,uint256)" TOKEN_ADDRESS AMOUNT --private-key OWNER_KEY --rpc-url BASE_RPC
```

## 📈 **Performance & Scaling**

### **Gas Optimization**
- [ ] **Contract deployment** gas estimation
- [ ] **Function calls** gas optimization
- [ ] **Event emission** efficiency
- [ ] **Storage layout** optimization

### **Listener Scaling**
- [ ] **Multiple instances** for redundancy
- [ ] **Load balancing** across listeners
- [ ] **Database connection** pooling
- [ ] **Queue processing** optimization

### **Backend Scaling**
- [ ] **Horizontal scaling** of API servers
- [ ] **Database read replicas** for queries
- [ ] **Caching layer** for frequent data
- [ ] **CDN** for static assets

## 🔍 **Post-Launch Validation**

### **Week 1 Monitoring**
- [ ] **Payment success rate** > 95%
- [ ] **Event processing** < 30s latency
- [ ] **Audit completion** > 90% success
- [ ] **Error rates** < 5%
- [ ] **Gas costs** within budget

### **Security Review**
- [ ] **Contract interactions** monitored
- [ ] **Admin function calls** logged
- [ ] **Suspicious activity** flagged
- [ ] **Access patterns** analyzed
- [ ] **Vulnerability scanning** scheduled

### **Performance Review**
- [ ] **Transaction throughput** measured
- [ ] **Gas efficiency** analyzed
- [ ] **Listener performance** optimized
- [ ] **Database performance** tuned
- [ ] **Scaling decisions** made

## 📚 **Documentation & Training**

### **Team Training**
- [ ] **Contract functions** explained
- [ ] **Emergency procedures** practiced
- [ ] **Monitoring tools** demonstrated
- [ ] **Escalation procedures** documented
- [ ] **Contact information** updated

### **User Documentation**
- [ ] **Payment flow** documented
- [ ] **Troubleshooting** guide created
- [ ] **FAQ** compiled
- [ ] **Support channels** established
- [ ] **Video tutorials** created

## 🎉 **Launch Checklist**

### **Final Verification**
- [ ] **Contract deployed** and verified
- [ ] **Listener running** and connected
- [ ] **Backend integrated** and tested
- [ ] **Monitoring active** and alerting
- [ ] **Team trained** and ready
- [ ] **Documentation complete** and accessible
- [ ] **Support channels** open and staffed

### **Launch Sequence**
1. **Deploy contract** to Base mainnet
2. **Verify contract** on BaseScan
3. **Start listener** and verify connection
4. **Test payment flow** with small amount
5. **Enable production** payments
6. **Monitor closely** for first 24 hours
7. **Scale up** based on demand

---

**Your UatuAudit payment system is production-ready!** 🚀

This checklist ensures a secure, scalable, and maintainable deployment. Follow each section systematically and validate before proceeding to the next step.

**Remember**: Security first, test thoroughly, monitor closely, and have emergency procedures ready! 🦉
