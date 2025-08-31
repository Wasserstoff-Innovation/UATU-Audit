# 🔒 UatuAudit - Complete Security Audit Platform

A comprehensive blockchain security auditing platform with wallet integration, GitHub OAuth, and automated report generation.

## ✨ Features Implemented

### 🔗 Frontend Integration
- **Base Blockchain Wallet Connection**: Connects to Base mainnet with MetaMask
- **Grid-based UI**: Professional 12x8 grid layout with hover effects
- **GitHub OAuth Flow**: Real GitHub authentication with popup handling
- **Mock Audit Testing**: Double-click GitHub button for local Solidity file testing
- **PDF Report Downloads**: Generated audit reports with security scores

### ⚡ Backend API
- **FastAPI Server**: High-performance async API server
- **GitHub OAuth**: Complete OAuth flow with user management
- **Webhook Support**: GitHub webhook handling for repository updates
- **Database Integration**: SQLAlchemy with user, audit job, and webhook models
- **Security Audit Engine**: Pattern-based analysis of Solidity contracts
- **PDF Generation**: Automated report creation and download

### 🧪 Mock Testing System
- **Existing Contract Analysis**: Uses `examples/sample.sol` and `examples/sensitive.sol`
- **Security Scoring**: Automated scoring based on code patterns
- **Vulnerability Detection**: Identifies common security issues
- **Gas Optimization**: Provides efficiency recommendations
- **Best Practices**: Suggests improvements for code quality

## 📁 Project Structure

```
UatuAudit/
├── backend/
│   ├── main.py              # FastAPI server
│   └── requirements.txt     # Python dependencies
├── auditor/dashboard/templates/
│   └── landing.html         # Main frontend interface
├── examples/
│   ├── sample.sol          # Basic counter contract
│   └── sensitive.sol       # Access control contract
├── test_outputs/           # Generated audit reports
├── .env.example           # Environment configuration
├── setup.py              # Complete platform setup
├── run_backend.py        # Backend server launcher
└── test_mock_audit.py    # Mock audit testing
```

## 🚀 Quick Start

### 1. Setup the Platform
```bash
python3 setup.py
```

### 2. Configure GitHub OAuth
1. Create a GitHub OAuth App:
   - Go to GitHub Settings → Developer settings → OAuth Apps
   - Set Authorization callback URL to: `http://localhost:8000/auth/github`
   - Copy your Client ID and Secret

2. Update `.env` file:
```env
GITHUB_CLIENT_ID=your_actual_client_id
GITHUB_CLIENT_SECRET=your_actual_client_secret
```

### 3. Start the Backend
```bash
python3 run_backend.py
```

### 4. Access the Platform
- **Frontend**: Open `auditor/dashboard/templates/landing.html` in browser
- **API Docs**: http://localhost:8000/docs
- **Backend**: http://localhost:8000

## 🔧 Testing

### Mock Audit Testing
```bash
# Run comprehensive mock audits
python3 test_mock_audit.py

# Check generated reports
ls test_outputs/
```

### Frontend Testing
1. Open landing page in browser
2. Click "Connect Wallet" → Connect MetaMask to Base network
3. **For Real GitHub**: Single-click "Connect GitHub"
4. **For Mock Testing**: Double-click "Connect GitHub" → Select contract → Run audit

## 🛡️ Security Features Detected

### ✅ Good Practices
- Access control modifiers (`onlyOwner`)
- Input validation (`require` statements)
- Event emissions for transparency
- Proper Solidity version specification

### ⚠️ Warnings Identified
- External calls without reentrancy protection
- Missing multi-signature for critical functions
- Insufficient documentation

### 🚨 Critical Issues
- Self-destruct functions without proper controls
- Unprotected state changes

## 📊 Audit Reports Include

- **Security Score**: 0-100 based on vulnerability analysis
- **Detailed Findings**: Categorized by severity (Critical/Warning/Info/Good)
- **Gas Optimization**: Efficiency improvement suggestions
- **Best Practices**: Code quality recommendations
- **Contract Metrics**: Lines of code, function count, modifier count

## 🔗 Integration Points

### GitHub Integration
- **OAuth Flow**: Complete user authentication
- **Repository Access**: Read user repos and branches
- **Webhooks**: Auto-trigger audits on code changes
- **Cloning**: Download repositories for analysis

### Blockchain Integration
- **Base Network**: Mainnet connection via MetaMask
- **Wallet Management**: Address display and connection status
- **USDC Payments**: Ready for payment integration (configured)

### Database Schema
- **Users**: GitHub user management
- **Audit Jobs**: Track audit status and results
- **Webhook Events**: Log GitHub events for processing

## 📝 Mock Data Examples

### Sample Contract Results
```
Security Score: 90/100
Findings: 3 (2 Good, 1 Info)
Gas Optimizations: 3 suggestions
Best Practices: 4 recommendations
```

### Sensitive Contract Results
```
Security Score: 93/100  
Findings: 3 (2 Good, 1 Info)
Access Control: ✅ Implemented
Input Validation: ✅ Present
```

## 🚀 Production Deployment

### Environment Variables
```env
# Production settings
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=postgresql://user:pass@localhost/uatu
SECRET_KEY=your-production-secret
JWT_SECRET_KEY=your-jwt-production-secret
```

### External Services Integration
- **GitHub App**: Create production GitHub App
- **Database**: PostgreSQL for production
- **File Storage**: AWS S3 for PDF reports
- **Monitoring**: Add logging and error tracking

## 🧪 Testing Results

The mock audit system successfully analyzed both example contracts:

1. **sample.sol**: 90/100 security score
   - ✅ Input validation present
   - ✅ Events emitted
   - ⚠️ Missing advanced features

2. **sensitive.sol**: 93/100 security score
   - ✅ Access control implemented
   - ✅ Proper state management
   - ⚠️ No multi-sig protection

## 📖 API Endpoints

- `GET /` - Health check
- `GET /auth/github` - GitHub OAuth callback
- `POST /api/audit/mock` - Start mock audit
- `GET /api/audit/{job_id}` - Get audit status
- `GET /api/audit/{job_id}/pdf` - Download PDF report
- `POST /webhooks/github` - GitHub webhook handler
- `GET /api/user/repos` - Get user repositories
- `GET /api/repos/{owner}/{repo}/branches` - Get repo branches

## 🎯 Next Steps

1. **Enhanced Analysis**: Integrate Slither, MythX, or custom analyzers
2. **Real-time Updates**: Implement WebSocket for live progress
3. **Payment System**: Complete USDC payment integration
4. **CI/CD Integration**: Add GitHub Actions for automated audits
5. **Multi-chain Support**: Extend beyond Base to other networks

---

🔒 **UatuAudit Platform** - Ship with Certainty!