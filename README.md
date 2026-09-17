# Pro RAG: Evidence-First Hallucination-Resistant RAG

## What is this?
A Retrieval-Augmented Generation system designed for strict evidence grounding.

## Why does it exist?
To validate generated claims against retrieved evidence and reject unsupported output under the evaluated release tests. It applies programmatic claim and citation validation before returning the response and falls back to a deterministic exact-match engine if the remote LLM fails, ensuring answers are structurally validated against the ingested data.

## Deployment States
- **Local Docker:** VERIFIED
- **GitHub:** VERIFIED
- **Render configuration:** VERIFIED
- **Public Render deployment:** NOT DEPLOYED
- **HTTPS public deployment:** NOT TESTED

## Quick Start (Docker Deployment)
1. Clone the repo.
2. cp .env.example .env and securely add your OPENAI_API_KEY.
3. docker compose -f docker-compose.prod.yml up -d --build
4. Visit http://localhost:80

## Architecture
- **Remote LLM Mode:** Uses gpt-4.1-mini to synthesize multi-concept answers with inline [S1] citations, validating every claim against the DB.
- **Local Fallback Mode:** If OpenAI is unreachable, an internal engine exactly extracts and concatenates relevant sentences based on lexical relevance, rejecting un-cited claims.

## Security
- Hardened against Prompt Injection: unsupported claims injected by adversarial prompts are rejected by the validation layer under the tested conditions.
- Contradiction handling intercepts conflicting retrieved facts to prevent contradictory output generation.

## Known Limitations
- The local fallback is rigid and may abstain from valid answers if the lexical semantic intent is poorly aligned.
- The public deployment requires manual GitHub authentication via Render.

## Deployment
- **Local Docker:** docker compose -f docker-compose.prod.yml up
- **Render:** Use ender.yaml + [RENDER_QUICKSTART.md](RENDER_QUICKSTART.md)

*Public deployment is pending until actually deployed on Render.*

### Documentation Links
- [RELEASE_NOTES.md](RELEASE_NOTES.md)
- [RENDER_QUICKSTART.md](RENDER_QUICKSTART.md)
- [RENDER_DEPLOYMENT_CHECKLIST.md](RENDER_DEPLOYMENT_CHECKLIST.md)
- [DEPLOYMENT_GUIDE_RENDER.md](DEPLOYMENT_GUIDE_RENDER.md)
- [POST_DEPLOY_VERIFICATION.md](POST_DEPLOY_VERIFICATION.md)
- [PUBLIC_DEMO_SCRIPT.md](PUBLIC_DEMO_SCRIPT.md)
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)

