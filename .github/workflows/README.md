# GitHub Actions Deployment Workflows

This directory contains GitHub Actions workflows for deploying the Receipt Splitter application to Fly.io.

## Workflows

### 1. Production Deployment (`fly-deploy.yml`)
- **Trigger**: Pushes to `main` branch or manual workflow dispatch
- **Purpose**: Deploys the application to production on Fly.io
- **App**: `receipt-splitter-demo`

### 2. PR Review Apps (`fly-review.yml`)
- **Trigger**: Pull request events (opened, reopened, synchronized, closed)
- **Purpose**: Creates temporary review apps for pull requests
- **App**: `receipt-splitter-pr-{PR_NUMBER}`
- **Region**: EWR (Eastern US)

## Setup Instructions

### 1. Generate Fly.io API Token
```bash
fly tokens create deploy -x 999999h
```
Copy the entire output including `FlyV1` prefix.

### 2. Add Token to GitHub Secrets
1. Go to repository Settings → Secrets and variables → Actions
2. Create new repository secret named `FLY_API_TOKEN`
3. Paste the token value from step 1

### 3. Verify Configuration
- Ensure `fly.toml` exists in repository root
- Check that app name in `fly.toml` matches your Fly.io app
- Confirm primary region is set correctly

## Manual Deployment
To trigger a manual deployment:
1. Go to Actions tab in GitHub
2. Select "Deploy to Fly.io" workflow
3. Click "Run workflow" button

## Review Apps
Review apps are automatically created for pull requests from the same repository (not forks). Each PR gets its own isolated environment at:
```
https://receipt-splitter-pr-{PR_NUMBER}.fly.dev
```

Review apps are automatically destroyed when the PR is closed.

## Troubleshooting

### Common Issues
- **Authentication Failed**: Verify `FLY_API_TOKEN` secret is set correctly
- **App Not Found**: Check app name in `fly.toml` matches Fly.io dashboard
- **Build Failures**: Review Dockerfile and ensure all dependencies are installed

### Monitoring Deployments
View deployment logs in:
- GitHub Actions tab for workflow runs
- Fly.io dashboard for application logs
- `fly logs` command for real-time monitoring