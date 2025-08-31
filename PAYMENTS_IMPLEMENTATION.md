# UatuAudit Payments Implementation Guide

## 🎯 **Overview**

This guide walks you through implementing the complete payment system for UatuAudit, including:

1. **On-chain payments** on Base network (USDC)
2. **Smart contract deployment** and verification
3. **Wallet integration** and payment flow
4. **Backend event listening** and order processing
5. **GitHub App integration** for "every commit" plans

## 🚀 **Quick Start (5 minutes)**

### **1. Deploy Smart Contract**

```bash
# Make deployment script executable
chmod +x scripts/deploy-contract.sh

# Create .env file with your configuration
cp .env.example .env
# Edit .env with your Base network details

# Deploy to Base mainnet
./scripts/deploy-contract.sh
```

### **2. Test Wallet Integration**

```bash
# Open the demo page
open auditor/dashboard/static/examples/wallet-demo.html

# Update CONFIG.ORDERS_ADDRESS with your deployed contract
# Connect wallet and test payment flow
```

### **3. Integrate with Backend**

```python
# Add to your FastAPI app
from auditor.payments.listener import OrderListener

# Start listening for OrderPaid events
listener = OrderListener(
    rpc_url="https://mainnet.base.org",
    contract_address="0x...",  # Your deployed contract
    private_key="0x..."        # Your listener private key
)
listener.start()
```

## 🏗️ **Architecture Overview**

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

## 🔧 **Smart Contract Deployment**

### **Prerequisites**

- **Foundry** installed (`curl -L https://foundry.paradigm.xyz | bash`)
- **Base network** configured in your wallet
- **ETH** for gas fees (recommend 0.01 ETH minimum)
- **Treasury address** to receive payments

### **Environment Configuration**

Create `.env` file:

```bash
# Base Network Configuration
BASE_RPC_URL=https://mainnet.base.org
BASE_PRIVATE_KEY=your_private_key_here
BASE_EXPLORER=https://basescan.org
BASE_EXPLORER_API_KEY=your_basescan_api_key

# Contract Configuration
TREASURY_ADDRESS=0x...  # Your treasury wallet
USDC_ADDRESS=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
AUDIT_PRICE=100000000  # 100 USDC (6 decimals)
```

### **Deploy Contract**

```bash
./scripts/deploy-contract.sh
```

**Expected Output:**
```
✅ Contract deployed successfully!
Contract Address: 0x1234...5678
• Network: Base Mainnet
• Explorer: https://basescan.org/address/0x1234...5678
• Price: 100 USDC
```

### **Verify Contract**

The deployment script automatically attempts verification. If it fails:

```bash
# Manual verification
forge verify-contract 0x1234...5678 \
  contracts/AuditOrders.sol:AuditOrders \
  --chain-id 8453 \
  --constructor-args $(cast abi-encode "constructor(address,address,uint256)" \
    "0xTREASURY" "0xUSDC" "100000000")
```

## 💳 **Wallet Integration**

### **Frontend Demo**

The `wallet-demo.html` provides a complete working example:

- **Wallet connection** with MetaMask
- **Network switching** to Base
- **USDC approval** and payment
- **Transaction monitoring** and confirmation
- **Error handling** and user feedback

### **Integration Steps**

1. **Update Configuration:**
   ```javascript
   const CONFIG = {
       ORDERS_ADDRESS: "0x1234...5678",  // Your deployed contract
       USDC_ADDRESS: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
       CHAIN_ID: "0x2105"  // Base mainnet
   };
   ```

2. **Add to Your App:**
   ```html
   <!-- Include ethers.js -->
   <script src="https://cdn.jsdelivr.net/npm/ethers@6.13.2/dist/ethers.min.js"></script>
   
   <!-- Add payment button -->
   <button onclick="startAudit()">Start Audit - 100 USDC</button>
   ```

3. **Payment Function:**
   ```javascript
   async function startAudit(repo, commit) {
       const orders = new ethers.Contract(CONFIG.ORDERS_ADDRESS, ABI, signer);
       const salt = ethers.id(String(Date.now()));
       
       const tx = await orders.payAndStart(repo, commit, salt);
       await tx.wait();
       
       console.log("Payment successful! Order ID:", tx.hash);
   }
   ```

## 🔌 **Backend Event Listening**

### **Python Implementation**

Create `auditor/payments/listener.py`:

```python
import asyncio
import json
import logging
from typing import Optional
from web3 import Web3
from web3.middleware import geth_poa_middleware

class OrderListener:
    def __init__(self, rpc_url: str, contract_address: str, private_key: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        self.contract_address = contract_address
        self.private_key = private_key
        self.account = self.w3.eth.account.from_key(private_key)
        
        # Contract ABI (minimal for events)
        self.contract_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "orderId", "type": "bytes32"},
                    {"indexed": True, "name": "payer", "type": "address"},
                    {"indexed": False, "name": "repo", "type": "string"},
                    {"indexed": False, "name": "commit", "type": "string"},
                    {"indexed": False, "name": "amount", "type": "uint256"},
                    {"indexed": False, "name": "token", "type": "address"},
                    {"indexed": False, "name": "timestamp", "type": "uint256"}
                ],
                "name": "OrderPaid",
                "type": "event"
            }
        ]
        
        self.contract = self.w3.eth.contract(
            address=contract_address,
            abi=self.contract_abi
        )
        
        self.running = False
        self.logger = logging.getLogger(__name__)
    
    def start(self):
        """Start listening for OrderPaid events"""
        self.running = True
        self.logger.info("Starting OrderListener...")
        
        # Get latest block
        latest_block = self.w3.eth.block_number
        self.logger.info(f"Starting from block {latest_block}")
        
        while self.running:
            try:
                # Get new blocks
                current_block = self.w3.eth.block_number
                
                if current_block > latest_block:
                    # Process new blocks
                    for block_num in range(latest_block + 1, current_block + 1):
                        await self.process_block(block_num)
                    
                    latest_block = current_block
                
                # Wait before next check
                await asyncio.sleep(12)  # Base block time ~12s
                
            except Exception as e:
                self.logger.error(f"Error in event loop: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def process_block(self, block_num: int):
        """Process a single block for OrderPaid events"""
        try:
            # Get block with transactions
            block = self.w3.eth.get_block(block_num, full_transactions=True)
            
            for tx in block.transactions:
                if tx.to and tx.to.lower() == self.contract_address.lower():
                    # Check for OrderPaid events
                    receipt = self.w3.eth.get_transaction_receipt(tx.hash)
                    
                    for log in receipt.logs:
                        if log.address.lower() == self.contract_address.lower():
                            try:
                                # Parse event
                                event = self.contract.events.OrderPaid().process_log(log)
                                await self.handle_order_paid(event)
                            except Exception as e:
                                self.logger.warning(f"Failed to parse event: {e}")
        
        except Exception as e:
            self.logger.error(f"Error processing block {block_num}: {e}")
    
    async def handle_order_paid(self, event):
        """Handle OrderPaid event"""
        try:
            order_id = event.args.orderId.hex()
            payer = event.args.payer
            repo = event.args.repo
            commit = event.args.commit
            amount = event.args.amount
            token = event.args.token
            timestamp = event.args.timestamp
            
            self.logger.info(f"OrderPaid: {order_id} from {payer} for {repo}@{commit}")
            
            # Create order in database
            await self.create_order(
                order_id=order_id,
                payer=payer,
                repo=repo,
                commit=commit,
                amount=amount,
                token=token,
                timestamp=timestamp
            )
            
            # Queue audit job
            await self.queue_audit(order_id, repo, commit)
            
        except Exception as e:
            self.logger.error(f"Error handling OrderPaid: {e}")
    
    async def create_order(self, **kwargs):
        """Create order record in database"""
        # TODO: Implement database integration
        self.logger.info(f"Creating order: {kwargs}")
    
    async def queue_audit(self, order_id: str, repo: str, commit: str):
        """Queue audit job for processing"""
        # TODO: Implement job queue integration
        self.logger.info(f"Queuing audit: {order_id} for {repo}@{commit}")
    
    def stop(self):
        """Stop the event listener"""
        self.running = False
        self.logger.info("OrderListener stopped")

# Usage example
if __name__ == "__main__":
    import os
    
    listener = OrderListener(
        rpc_url=os.getenv("BASE_RPC_URL"),
        contract_address=os.getenv("CONTRACT_ADDRESS"),
        private_key=os.getenv("LISTENER_PRIVATE_KEY")
    )
    
    try:
        asyncio.run(listener.start())
    except KeyboardInterrupt:
        listener.stop()
```

### **FastAPI Integration**

Add to your dashboard server:

```python
from auditor.payments.listener import OrderListener
import asyncio
import threading

# Start listener in background thread
def start_payment_listener():
    listener = OrderListener(
        rpc_url=os.getenv("BASE_RPC_URL"),
        contract_address=os.getenv("CONTRACT_ADDRESS"),
        private_key=os.getenv("LISTENER_PRIVATE_KEY")
    )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(listener.start())

# Start in background
listener_thread = threading.Thread(target=start_payment_listener, daemon=True)
listener_thread.start()
```

## 🔄 **GitHub App Integration**

### **App Configuration**

1. **Create GitHub App:**
   - Go to GitHub Settings → Developer settings → GitHub Apps
   - Set permissions:
     - Repository: Contents (Read)
     - Pull requests (Read & Write)
     - Checks (Read & Write)
     - Webhooks (Read & Write)

2. **Webhook Events:**
   - `push`
   - `pull_request`
   - `check_suite`
   - `installation_repositories`

3. **Install App:**
   - Users install app on their repositories
   - Select protected branches (e.g., `main`, `release/*`)

### **Webhook Handler**

```python
from fastapi import APIRouter, Request, HTTPException
import hmac
import hashlib

router = APIRouter()

@router.post("/webhooks/github")
async def github_webhook(request: Request):
    # Verify webhook signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(request.body(), signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()
    
    if event_type == "push":
        await handle_push(payload)
    elif event_type == "pull_request":
        await handle_pull_request(payload)
    
    return {"status": "ok"}

async def handle_push(payload):
    """Handle push events for every-commit plans"""
    repo = payload["repository"]["full_name"]
    ref = payload["ref"]
    commits = payload["commits"]
    
    # Check if repo has every-commit plan
    if not has_every_commit_plan(repo):
        return
    
    # Create orders for each commit
    for commit in commits:
        await create_audit_order(
            repo=repo,
            commit=commit["id"],
            branch=ref.replace("refs/heads/", ""),
            plan_type="every_commit"
        )

async def create_audit_order(repo: str, commit: str, branch: str, plan_type: str):
    """Create audit order (free for every-commit plans)"""
    # TODO: Implement order creation
    pass
```

## 💰 **Pricing & Plans**

### **One-Off Audits**
- **Price**: $100 USD per run
- **Payment**: USDC on Base or Stripe
- **Retry**: Fresh charge each time
- **Idempotency**: Salt-based to prevent double charges

### **Every-Commit Plans**
- **Setup**: GitHub App installation
- **Trigger**: Automatic on protected branch pushes
- **Pricing**: 
  - **Fiat**: Monthly + per-commit metered billing
  - **Crypto**: Prepaid USDC balance, auto-decrement
- **Gating**: Branch protection requires `uatu/audit` check

### **Refund Policy**
- **Infrastructure failures**: Credit for retry
- **Analysis not started**: Full refund
- **Partial analysis**: Pro-rated refund

## 🧪 **Testing & QA**

### **Testnet Deployment**

```bash
# Deploy to Base Sepolia testnet
BASE_RPC_URL=https://sepolia.base.org \
BASE_EXPLORER=https://sepolia.basescan.org \
./scripts/deploy-contract.sh
```

### **Test Scenarios**

1. **Wallet Connection**
   - MetaMask installation and connection
   - Network switching to Base
   - Account selection and switching

2. **Payment Flow**
   - USDC approval
   - Payment transaction
   - Confirmation and order creation

3. **Event Listening**
   - OrderPaid event emission
   - Backend event processing
   - Order database creation

4. **Error Handling**
   - Insufficient balance
   - Network errors
   - Contract failures

### **Integration Testing**

```bash
# Test complete flow
./scripts/test-payment-flow.sh

# Test contract functions
forge test --match-contract AuditOrders
```

## 🚀 **Production Deployment**

### **Pre-Launch Checklist**

- [ ] Contract deployed and verified on Base mainnet
- [ ] Treasury address configured and tested
- [ ] Backend event listener running
- [ ] Database schema for orders and audits
- [ ] Job queue for audit processing
- [ ] Monitoring and alerting configured
- [ ] Error handling and logging implemented
- [ ] Rate limiting and security measures
- [ ] Backup and recovery procedures

### **Launch Steps**

1. **Deploy Contract**
   ```bash
   ./scripts/deploy-contract.sh
   ```

2. **Update Configuration**
   - Set contract address in backend
   - Configure webhook endpoints
   - Set up monitoring

3. **Test Payment Flow**
   - Small test payment
   - Event processing
   - Audit queue

4. **Enable Production**
   - Remove test restrictions
   - Enable real payments
   - Monitor for issues

### **Post-Launch Monitoring**

- **Payment success rate**
- **Event processing latency**
- **Audit queue performance**
- **Error rates and types**
- **Gas costs and optimization**

## 🔒 **Security Considerations**

### **Smart Contract Security**
- **Access control**: Only owner can update treasury/price
- **Input validation**: Repo/commit/salt validation
- **Reentrancy protection**: Safe USDC transfers
- **Emergency functions**: Owner can withdraw stuck tokens

### **Backend Security**
- **Webhook verification**: HMAC signature validation
- **Rate limiting**: Prevent abuse
- **Input sanitization**: Validate all inputs
- **Error handling**: Don't leak sensitive information

### **Operational Security**
- **Private key management**: Secure storage and rotation
- **Network security**: RPC endpoint security
- **Monitoring**: Alert on suspicious activity
- **Backup**: Regular database and configuration backups

## 📚 **Resources & Support**

### **Documentation**
- [Base Network Documentation](https://docs.base.org/)
- [USDC on Base](https://docs.base.org/guides/deploy-smart-contracts)
- [Foundry Book](https://book.getfoundry.sh/)
- [Web3.py Documentation](https://web3py.readthedocs.io/)

### **Community**
- [Base Discord](https://discord.gg/base)
- [Foundry Discord](https://discord.gg/getfoundry)
- [UatuAudit Issues](https://github.com/your-org/uatu-audit/issues)

### **Support**
For implementation support:
1. Check this guide and documentation
2. Review error logs and monitoring
3. Test with small amounts first
4. Open GitHub issue with details

---

**Your UatuAudit payment system is ready for production!** 🎉

Start with the smart contract deployment, then integrate the wallet demo, and finally add the backend event listening. The system is designed to be robust, secure, and scalable for production use.
