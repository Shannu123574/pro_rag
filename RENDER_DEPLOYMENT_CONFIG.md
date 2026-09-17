# RENDER DEPLOYMENT CONFIGURATION

- **Repository:** https://github.com/Shannu123574/pro_rag
- **Branch:** main
- **Blueprint:** Corrected ender.yaml with valid untime: docker and correct contexts.
- **Database wiring:** romDatabase with connectionString (internal networking).
- **Docker runtime:** untime: docker is used instead of the deprecated env: docker.
- **Docker contexts:** API context is ., frontend context is ./frontend.
- **Frontend/API strategy:** VITE_API_URL is set to sync: false meaning it must be injected in the Render dashboard after the API service is provisioned.
- **Secrets:** OPENAI_API_KEY is set to sync: false.
- **Health check:** Verified API healthcheck on /health.
- **Local Docker validation:** VERIFIED LOCALLY
- **Render official validation:** Render CLI = NOT AVAILABLE, Local structural validation = PASS

> **Status:** RENDER DEPLOYMENT NOT YET EXECUTED
