# Environment Setup Guide

## 🔧 **Environment Configuration**

UatuAudit uses environment variables for configuration. Follow these steps to set up your environment:

### **1. Copy Environment Template**

```bash
cp .env.example .env
```

### **2. Configure GitHub OAuth**

#### **Create GitHub OAuth App:**

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **"New OAuth App"**
3. Fill in the details:
   - **Application name**: `UatuAudit`
   - **Homepage URL**: `http://localhost:8080`
   - **Authorization callback URL**: `http://localhost:8080/auth/github`
4. Copy the **Client ID** and **Client Secret**

#### **Update .env file:**

```bash
GITHUB_CLIENT_ID=your_actual_github_client_id
GITHUB_CLIENT_SECRET=your_actual_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:8080/auth/github
```

### **3. Configure Security Keys**

Generate secure keys for production:

```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update .env
SECRET_KEY=your_generated_secret_key
JWT_SECRET_KEY=your_generated_jwt_secret_key
```

### **4. Environment Variables Reference**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GITHUB_CLIENT_ID` | GitHub OAuth Client ID | - | ✅ |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth Client Secret | - | ✅ |
| `GITHUB_REDIRECT_URI` | OAuth redirect URL | `http://localhost:8080/auth/github` | ✅ |
| `SECRET_KEY` | Application secret key | - | ✅ |
| `JWT_SECRET_KEY` | JWT signing key | - | ✅ |
| `API_BASE_URL` | Backend API URL | `http://localhost:8000` | ❌ |
| `FRONTEND_URL` | Frontend URL | `http://localhost:8080` | ❌ |
| `DATABASE_URL` | Database connection string | `sqlite:///./uatu_audit.db` | ❌ |
| `DEBUG` | Enable debug mode | `false` | ❌ |
| `ENVIRONMENT` | Environment name | `production` | ❌ |
| `DASHBOARD_PORT` | Dashboard port | `8080` | ❌ |
| `API_PORT` | API port | `8000` | ❌ |
| `DEFAULT_AUDIT_PRICE_USDC` | Default audit price | `200` | ❌ |
| `MAX_AUDIT_TIME_SECONDS` | Max audit time | `30` | ❌ |
| `PAYMENT_PROVIDER` | Payment provider | `base` | ❌ |
| `USDC_CONTRACT_ADDRESS` | USDC contract address | Base mainnet address | ❌ |

### **5. Production Setup**

For production deployment:

1. **Set strong secrets:**
   ```bash
   SECRET_KEY=long-random-string-for-production
   JWT_SECRET_KEY=another-long-random-string
   ```

2. **Use production URLs:**
   ```bash
   FRONTEND_URL=https://your-domain.com
   GITHUB_REDIRECT_URI=https://your-domain.com/auth/github
   ```

3. **Disable debug:**
   ```bash
   DEBUG=false
   ENVIRONMENT=production
   ```

### **6. Development vs Production**

#### **Development (.env):**
```bash
DEBUG=true
ENVIRONMENT=development
FRONTEND_URL=http://localhost:8080
```

#### **Production:**
```bash
DEBUG=false
ENVIRONMENT=production
FRONTEND_URL=https://your-domain.com
```

### **7. Docker Compose Integration**

The `docker-compose.yml` automatically reads from your `.env` file. No additional configuration needed.

### **8. Testing GitHub OAuth**

1. Ensure your `.env` file has valid GitHub credentials
2. Start the application: `docker-compose up -d dashboard`
3. Visit: `http://localhost:8080`
4. Test the GitHub OAuth flow

### **9. Troubleshooting**

#### **GitHub OAuth Issues:**
- Verify callback URL matches exactly
- Check Client ID and Secret are correct
- Ensure GitHub app is not suspended

#### **Environment Loading Issues:**
- Verify `.env` file exists in project root
- Check file permissions
- Restart Docker containers after changes

#### **Port Conflicts:**
- Change `DASHBOARD_PORT` if 8080 is in use
- Update `docker-compose.yml` if needed

---

**🚀 Ready to audit with confidence!**
