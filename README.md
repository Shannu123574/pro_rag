# Pro RAG: Evidence-First Hallucination-Resistant RAG

## What is this?
An enterprise-grade Retrieval-Augmented Generation system. 

## Why does it exist?
To guarantee that LLM output is strictly grounded in retrieved evidence. It mathematically strips un-cited claims and falls back to a deterministic exact-match engine if the remote LLM fails, ensuring answers are 100% structurally validated.

## Quick Start (Docker Deployment)
1. Clone the repo.
2. cp .env.example .env and add your OPENAI_API_KEY.
3. docker compose -f docker-compose.prod.yml up -d --build
4. Visit http://localhost:80

## Architecture
- **Remote LLM Mode:** Uses gpt-4.1-mini to synthesize multi-concept answers with inline [S1] citations, validating every claim against the DB.
- **Local Fallback Mode:** If OpenAI is unreachable, an internal engine exactly extracts and concatenates relevant sentences without hallucinating.

## Security
- Hardened against Prompt Injection (injections lack valid citations and are stripped).
- Contradiction handling prevents returning conflicting data.

## Known Limitations
- The local fallback is rigid and may abstain from valid answers if the lexical semantic intent is poorly aligned.
- Not designed to be exposed directly to the public internet without a reverse proxy.
