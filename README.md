# Pro RAG — Production-Grade RAG System

An evidence-first Retrieval-Augmented Generation (RAG) system engineered for production use, featuring strict factual grounding, robust abstention, deterministic answering, and full observability.

## Architecture

Pro RAG implements a multi-stage RAG architecture prioritizing correctness and evidence integrity over uncontrolled LLM generation.

### Ingestion Flow
`Document -> Extraction -> Text Cleaning -> Chunking -> Dense Embedding -> pgvector + Full Text Search (PostgreSQL)`
- Idempotent document indexing with duplicate handling.
- Robust parsing for PDF, TXT, and MD files.
- Resilient against non-UTF8 files and empty documents.

### Retrieval Flow
`Query Expansion -> Dense Search -> Lexical Search -> Reciprocal Rank Fusion (RRF) -> Cross-Encoder Reranking`
- **Dense Model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- **Lexical Search**: PostgreSQL `to_tsvector` and `websearch_to_tsquery`
- **Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2` (CPU optimized)
- Targeted query expansion enriches queries using domain-specific rules.

### Generation Flow
`Reranked Candidates -> Evidence Sufficiency Gate -> Deterministic Fallback -> FLAN-T5 Generation -> Citation Validation`
- **Evidence Sufficiency Gate**: Drops queries when top retrieved chunks score below 0.0 (unrelated).
- **Deterministic Rules**: Runs deterministic pattern-matching first for verifiable and exact facts (e.g. schedules, procedures).
- **Generator**: `google/flan-t5-base`. Instructed to explicitly declare missing evidence or conflicting evidence.
- **Abstention**: Deterministic abstention ("I don't have sufficient evidence in the knowledge base to answer that.") without hallucinated citations.

## Quick Start

1. **Clone the repository.**
2. **Environment**: Copy `.env.example` to `.env`. (Note: The current architecture utilizes local HuggingFace models, meaning external API keys are not required for generation/embedding).
3. **Start the environment**:
   ```bash
   docker compose up -d --build
   ```
4. **Access the frontend**: Open `http://localhost:5173`
5. **Access API documentation**: Open `http://localhost:8000/docs`
6. **Ingest sample documents**:
   Upload files directly from the React frontend, or run:
   ```bash
   docker compose exec api python -m app.cli ingest /app/data/sample
   ```

## API Endpoints

- `GET /health`: API status (`ok` or `warming_up`).
- `POST /ingest`: Upload documents (multipart/form-data).
- `GET /documents`: List ingested files.
- `DELETE /documents/{document_id}`: Remove an ingested file and chunks.
- `POST /query`: Send a question.
- `GET /history`: View past queries.
- `GET /analytics`: Metrics including retrieval/generation latencies, grounded rates, and abstention accuracy.
- `GET /evaluation`: Trigger the benchmark test suite.

## Evaluation & Benchmarks

The project includes an evaluation suite (`tests/test_rag.py`) featuring end-to-end questions containing golden (answerable) queries and abstention (unsupported) queries, alongside adversarial conditions like paraphrases, direct questions, short queries, and terminology changes.

**Current Verified Metrics:**
- **Recall@1**: 100% (Target >= 0.80)
- **Recall@6**: 100%
- **MRR**: 100% (Target >= 0.80)
- **Citation Correctness**: 100%
- **Answer Grounding**: 100%
- **Abstention Accuracy**: 100%
- **Average Warm Latency**: < 500 ms (Target < 1.0s)

To run the test suite:
```bash
docker compose exec api pytest -q tests/test_rag.py
```

## Resilience & Reliability

- **API Startup**: Asynchronous lazy loading of models in the background thread. Fast Uvicorn port binding returning HTTP 503 during warmup.
- **Database**: PostgreSQL uses `pg_isready` healthcheck. API and Frontend wait for database connection readiness and implement connection retry-loops to survive restarts.
- **Frontend**: Handles DB unavailability, API downtime, and model warmup periods with explicit UI indicators instead of crashing.
- **Security**: Strict query regex boundaries, max sizes, and sanitization.

## API Contracts & OpenAPI

The backend features rigorous Pydantic API response models mapping 1:1 with actual outputs, ensuring the `/docs` OpenAPI schema is 100% accurate.
All responses are strict objects (e.g. `QueryResponse`, `HistoryItemSchema`, `AnalyticsResponse`). Errors return a standard `APIErrorResponse` containing `code`, `message`, and `request_id`.

## Continuous Integration & Release

To run the full E2E, Ingestion, adversarial RAG, and Security tests locally:
```bash
bash scripts/ci.sh
```
A demo workflow is described in `demo_runbook.md`.

## Troubleshooting

- **503 Service Unavailable (Frontend)**: This typically happens during container startup when models are downloading into the API cache. The UI will automatically resolve when the models finish warming up.
- **No readable text found**: Ensure your PDF is text-searchable (not scanned images) and your TXT files are valid UTF-8.
- **Database Connection Error**: The `db` container might be restarting or taking longer. Docker Compose will continually restart the API until the database is healthy.
