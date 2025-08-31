# UatuAudit Production Deployment Guide

## 🚀 **Production-Ready Features**

UatuAudit is now production-ready with the following enterprise features:

### **1. Professional PDF Reports**
- **Cover pages** with Uatu branding and status badges
- **Executive summaries** with key metrics and trends
- **Professional layout** with A4 formatting and pagination
- **Status badges** showing primary and secondary risk indicators
- **Generated automatically** with `--pdf on` flag

### **2. Enhanced Status Badge System**
- **Primary badges**: Critical, Dangerous, Needs Fixes, Passed Audit, Ready to Go
- **Secondary badges**: Trend Worsening, Static Failed, Tests Incomplete, Gas Heavy, LLM Assisted
- **Deterministic logic** based on risk scores, test results, and EoP coverage
- **Professional colors** following industry standards

### **3. Production Dashboard**
- **GitHub OAuth** authentication
- **Access control** via organization membership or email whitelist
- **Read-only audit browsing** with search and filtering
- **Portfolio overview** with badges and sparklines
- **File downloads** (PDF, HTML, CSV)
- **Responsive design** with professional styling

### **4. CI/CD Integration**
- **Multi-contract matrix** auditing
- **Risk gating** against versioned baselines
- **PDF generation** in CI pipeline
- **Badge embedding** in PR comments
- **Portfolio aggregation** across contracts
- **Soft-fail mode** for non-blocking issues

## 🛠 **Deployment Steps**

### **Step 1: Environment Configuration**

Create `dashboard.env` with your production values:

```bash
# Security
APP_SECRET=your-32-plus-character-random-secret-key-here
SECRET_KEY=your-32-plus-character-random-secret-key-here

# OAuth Configuration
OAUTH_PROVIDER=github
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# Access Control (choose one or both)
ALLOWED_EMAILS=admin@company.com,security@company.com
ALLOWED_ORGS=your-github-org-name

# Dashboard Settings
AUDITS_ROOT=/work/out
PORT=8080
HOST=0.0.0.0
```

### **Step 2: GitHub OAuth Setup**

1. Go to GitHub Settings → Developer settings → OAuth Apps
2. Create new OAuth App:
   - **Application name**: UatuAudit Dashboard
   - **Homepage URL**: `https://audits.yourdomain.com`
   - **Authorization callback URL**: `https://audits.yourdomain.com/auth/callback`
3. Copy Client ID and Client Secret to `dashboard.env`

### **Step 3: Deploy Dashboard**

```bash
# Make deployment script executable
chmod +x deploy-dashboard.sh

# Deploy (this will build image and start dashboard)
./deploy-dashboard.sh
```

### **Step 4: Reverse Proxy Setup**

Create nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name audits.yourdomain.com;
    
    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### **Step 5: SSL Certificate**

```bash
# Using Let's Encrypt
sudo certbot --nginx -d audits.yourdomain.com

# Or using cert-manager (Kubernetes)
kubectl apply -f cert-manager.yaml
```

## 🔒 **Security Features**

### **Authentication**
- GitHub OAuth with organization/email validation
- Session-based authentication with secure cookies
- CSRF protection and secure headers

### **Access Control**
- Organization membership validation
- Email domain whitelisting
- Read-only access to audit results

### **Data Protection**
- No sensitive data in logs
- Environment-based configuration
- Secure session management

## 📊 **Monitoring & Maintenance**

### **Health Checks**
```bash
# Dashboard health
curl https://audits.yourdomain.com/health

# Docker status
docker compose ps dashboard

# Logs
docker compose logs -f dashboard
```

### **Updates**
```bash
# Pull latest code
git pull origin main

# Rebuild and redeploy
./deploy-dashboard.sh
```

### **Backup**
```bash
# Backup baselines (critical for CI gating)
tar -czf baselines-$(date +%Y%m%d).tar.gz baseline/

# Backup configuration
cp dashboard.env dashboard.env.backup
```

## 🚨 **Troubleshooting**

### **Common Issues**

1. **Dashboard won't start**
   - Check `dashboard.env` configuration
   - Verify GitHub OAuth credentials
   - Check Docker logs: `docker compose logs dashboard`

2. **OAuth redirect fails**
   - Verify callback URL in GitHub OAuth app
   - Check nginx proxy configuration
   - Ensure HTTPS is properly configured

3. **PDF generation fails**
   - Check WeasyPrint dependencies in Docker
   - Verify font availability
   - Check disk space for temporary files

4. **CI pipeline fails**
   - Verify baseline files are committed
   - Check risk thresholds in workflow
   - Review soft-fail configuration

### **Log Analysis**
```bash
# Dashboard logs
docker compose logs dashboard | grep ERROR

# Audit logs
docker compose logs dashboard | grep "audit"

# OAuth logs
docker compose logs dashboard | grep "oauth"
```

## 📈 **Performance Tuning**

### **Dashboard Performance**
- **Cache TTL**: Adjust `DASHBOARD_CACHE_TTL` in `dashboard.env`
- **Refresh interval**: Set `DASHBOARD_REFRESH_INTERVAL` for file scanning
- **Worker processes**: Scale with multiple dashboard instances

### **PDF Generation**
- **Font optimization**: Use system fonts for faster rendering
- **Image compression**: Optimize SVG badges and logos
- **Memory limits**: Adjust Docker memory allocation for large reports

## 🔄 **CI/CD Integration**

### **GitHub Actions**
- **Matrix builds** for multi-contract auditing
- **Risk gating** against versioned baselines
- **Artifact uploads** with PDF reports
- **PR comments** with badges and sparklines

### **Baseline Management**
- **Automatic updates** on main branch pushes
- **Version control** for risk thresholds
- **Historical tracking** for trend analysis

## 📚 **API Reference**

### **Dashboard Endpoints**
- `GET /` - Main dashboard
- `GET /health` - Health check
- `GET /runs` - Audit runs listing
- `GET /portfolio` - Portfolio overview
- `GET /run/{ts}` - Individual run details
- `GET /download/pdf/{ts}` - PDF download
- `GET /download/portfolio/pdf` - Portfolio PDF

### **Authentication Endpoints**
- `GET /login` - Login page
- `GET /auth/github` - GitHub OAuth initiation
- `GET /auth/callback` - OAuth callback
- `GET /logout` - Logout

## 🎯 **Next Steps**

1. **Deploy dashboard** to production environment
2. **Configure monitoring** and alerting
3. **Set up backup** procedures for baselines
4. **Train team** on dashboard usage
5. **Monitor performance** and tune as needed

## 📞 **Support**

For production support:
- Check logs and health endpoints
- Review troubleshooting section
- Test with `./test-system.sh`
- Verify configuration in `dashboard.env`

---

**UatuAudit is production-ready with enterprise-grade features for professional contract auditing!** 🎉
