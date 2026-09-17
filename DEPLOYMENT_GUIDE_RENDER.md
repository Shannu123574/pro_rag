# DEPLOYMENT GUIDE (RENDER)

## Deployment Tier: FREE / DEMO
- **Web Service:** Free
- **Postgres:** Free

### Expected Limitations:
- 15-minute idle spin-down
- cold startup delay
- 1 GB Postgres
- 30-day Postgres expiration
- no Postgres backups

*This is a Hackathon / prototype deployment, not 24/7 production infrastructure.*

## Status
- LOCAL DOCKER = VERIFIED
- GITHUB = VERIFIED
- RENDER CONFIG = VERIFIED
- PUBLIC RENDER DEPLOYMENT = NOT YET COMPLETED

## Prerequisites
1. A GitHub account with the pro_rag repository pushed.
2. A Render.com account.
3. An OpenAI API Key.

## Deployment Steps (Blueprint)
1. In the Render Dashboard, click **New** -> **Blueprint**.
2. Connect your GitHub repository.
3. Render will parse the ender.yaml file in the root.
4. It will prompt you to enter the value for OPENAI_API_KEY. Enter your OpenAI key securely.
5. Click **Apply**. Render will automatically provision:
   - A private PostgreSQL instance (with pgvector).
   - The FastAPI backend service (pro-rag-api).
   - The Vite Frontend service (pro-rag-frontend).
6. Once deployed, the frontend will be available over managed HTTPS at the provided URL.

## Rollback
- Push an older commit to the main branch. Render will auto-deploy the previous image cleanly.

