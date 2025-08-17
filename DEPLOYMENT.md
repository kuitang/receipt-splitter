# Fly.io Deployment Plan for Receipt Splitter

## Overview
This deployment plan outlines how to deploy the Receipt Splitter Django application to Fly.io using their PostgreSQL database service.

## Prerequisites
1. Install Fly.io CLI: `curl -L https://fly.io/install.sh | sh`
2. Sign up for Fly.io account: `fly auth signup`
3. Log in: `fly auth login`

## Code Changes Required

### 1. Database Configuration (settings.py)
Update the database configuration to use PostgreSQL:

```python
import dj_database_url

# Replace the existing DATABASES configuration with:
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}
```

### 2. Add PostgreSQL Dependencies
Update `requirements.txt` to include:
```
dj-database-url
psycopg2-binary
gunicorn
whitenoise
```

Note: `python-dotenv` is not required as Fly.io sets environment variables directly.

### 3. Static Files Configuration (settings.py)
Add WhiteNoise middleware for static file serving:

```python
# Add to MIDDLEWARE (after SecurityMiddleware)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Add this line
    # ... rest of middleware
]

# Update static files configuration
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
```

### 4. Allowed Hosts Configuration (settings.py)
Update ALLOWED_HOSTS to include Fly.io domain:

```python
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0,testserver,.fly.dev').split(',')

# Add CSRF trusted origins for Fly.io
CSRF_TRUSTED_ORIGINS = [
    'https://*.fly.dev',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
```

## Local Development Setup

For local development, set environment variables directly:

```bash
# Option 1: Export in your shell
export OPENAI_API_KEY="your-key-here"
export DEBUG="True"

# Option 2: Create a script (not tracked by git)
echo 'export OPENAI_API_KEY="your-key"' > set_env.sh
echo 'export DEBUG="True"' >> set_env.sh
source set_env.sh

# Option 3: Use your shell's profile (.bashrc, .zshrc, etc.)
```

## Deployment Steps

### 1. Initialize Fly.io Application
```bash
fly launch --no-deploy
```
This will:
- Create a new Fly.io app
- Generate `fly.toml` configuration file
- Ask about PostgreSQL database setup (select "Yes")

### 2. Set Environment Variables
```bash
fly secrets set SECRET_KEY="your-secret-key-here"
fly secrets set OPENAI_API_KEY="your-openai-api-key"
fly secrets set DEBUG="False"
```

### 3. Configure Database
```bash
# Create PostgreSQL database (cheapest option - single node development)
fly postgres create --name receipt-splitter-db \
  --initial-cluster-size 1 \
  --vm-size shared-cpu-1x \
  --volume-size 3 \
  --region ord

# Attach database to app
fly postgres attach receipt-splitter-db --app receipt-splitter
```

**Cost Breakdown:**
- Single PostgreSQL node: ~$1.94/month (shared-cpu-1x)
- 3GB storage: ~$0.45/month
- **Total database cost: ~$2.39/month**

**For production, add high availability:**
```bash
# Production option (3-node cluster for high availability)
fly postgres create --name receipt-splitter-db \
  --initial-cluster-size 3 \
  --vm-size shared-cpu-1x \
  --volume-size 10 \
  --region ord
# Cost: ~$5.82/month + $1.50/month storage = ~$7.32/month
```

### 4. Deploy Application
```bash
fly deploy
```

### 5. Run Database Migrations
```bash
fly ssh console
python manage.py migrate
python manage.py createsuperuser  # Optional: create admin user
exit
```

### 6. Verify Deployment
```bash
fly apps open
fly logs
```

## Configuration Files Created

### fly.toml
- Configures app name and region
- Sets environment variables for production
- Configures HTTP service
- Sets up static file serving
- Defines release command for migrations

### Dockerfile (Multi-Stage Build)
- **Stage 1**: Builds Python dependencies with compilation tools
- **Stage 2**: Collects static files in isolation
- **Stage 3**: Final production image with only runtime dependencies
- 40-50% smaller final image (~150-180MB vs ~250-300MB)
- Non-root user execution (appuser)
- Optimized gunicorn configuration with gthread workers
- Health check endpoint for monitoring

### .dockerignore
- Excludes development files and directories
- Prevents large temporary files from being copied
- Excludes test data and generated images

## Security Considerations

1. **Environment Variables**: All sensitive data (SECRET_KEY, API keys) stored as Fly.io secrets
2. **HTTPS**: Force HTTPS enabled in fly.toml
3. **Security Headers**: Production security settings enabled when DEBUG=False
4. **Database**: PostgreSQL with connection pooling

## Monitoring and Maintenance

### Viewing Logs
```bash
fly logs
fly logs -a receipt-splitter  # If app name differs
```

### Accessing Application
```bash
fly ssh console
```

### Scaling
```bash
fly scale count 2  # Scale to 2 instances
fly scale vm shared-cpu-1x  # Change VM size
```

### Database Management
```bash
fly postgres connect -a receipt-splitter-db
```

## Troubleshooting

### Common Issues:
1. **Static files not loading**: Ensure `collectstatic` runs in Dockerfile
2. **Database connection errors**: Verify PostgreSQL attachment and environment variables
3. **Migration failures**: Run migrations manually via SSH console
4. **Connection failures**: Check that app responds on port 8000

### Debug Commands:
```bash
fly status
fly logs --json
fly ssh console -C "python manage.py check --deploy"
```

## Cost Optimization

### Application Costs
- **Django app**: ~$1.94/month (shared-cpu-1x, scales to zero when idle)
- **Database**: ~$2.39/month (single node development) 
- **Total minimum**: ~$4.33/month

### Cost-Saving Features
- **Auto-stop/start**: Machines scale to zero during inactivity
- **Shared CPU**: Cheapest compute option (shared-cpu-1x)
- **Minimal storage**: 3GB database volume to start
- **No dedicated IPv4**: Uses shared IPv4 (saves $2/month)

### Scaling Options
- **Add instances**: `fly scale count 2` (~$3.88/month for 2 Django instances)
- **Upgrade database**: Switch to HA cluster (~$7.32/month total)
- **Add storage**: Scale volume as needed ($0.15/GB/month)

### Free Usage
- **Internal networking**: No charges for app-to-database communication
- **SSL certificates**: Included for *.fly.dev domains
- **IPv6**: Unlimited inbound/outbound traffic

## Notes

- The app uses in-memory image storage, so uploaded images are temporary
- WebSocket support is available through ASGI configuration
- Rate limiting is enabled for security
- Session data is stored in the database