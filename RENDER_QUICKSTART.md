# RENDER QUICKSTART

The application is fully configured for Render.com via the ender.yaml Blueprint.

## Deployment Procedure

1. **GitHub:** Ensure your local repository is pushed to a GitHub repository that you own.
2. **Render Dashboard:** Log into [Render.com](https://render.com).
3. **Create Blueprint:** Click **New** -> **Blueprint**.
4. **Select Repository:** Connect and select your GitHub repository.
5. **Confirm Configuration:** Render will automatically parse ender.yaml and identify the API, Frontend, and PostgreSQL instances.
6. **Configure Secrets:** When prompted by the Render dashboard, securely paste your OPENAI_API_KEY.
7. **Deploy:** Click **Apply**.
8. **Wait for Readiness:** Wait for the API and PostgreSQL services to finish provisioning, and for the pro-rag-frontend service to show **Live**.
9. **Open Frontend URL:** Open the provided https://pro-rag-frontend.onrender.com URL in your browser.
10. **Run Verification:** Follow the steps in POST_DEPLOY_VERIFICATION.md to ensure the live environment functions correctly.

> **Status:** The current repository is NOT YET publicly deployed. It is DEPLOYMENT-READY.
