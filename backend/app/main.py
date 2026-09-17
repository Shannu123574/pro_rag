from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Request,
)

from pydantic import BaseModel, Field
from app.schemas import (
    StatusResponse, QueryRequest, QueryResponse, IngestResponse,
    DocumentSchema, HistoryItemSchema, AnalyticsResponse, EvaluationResponse, ErrorResponse
)

from pathlib import Path

from sqlalchemy import (
    func,
    text,
)

import tempfile
import time
import subprocess
import re
import os
import json


from app.db import (
    init_db,
    SessionLocal,
    Chunk,
    QueryLog,
)

from app.ingest import ingest_file

from app.retrieval import (
    retrieve,
    retrieve_with_diagnostics,
    get_embedding_model,
    get_reranker,
)

from app.generation import answer
from app.logger import setup_logger, request_id_var, endpoint_var, generate_request_id
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

app_logger = setup_logger("main")
class APIError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message}
        )

# Categories
VALIDATION_ERROR = "VALIDATION_ERROR"
INGESTION_ERROR = "INGESTION_ERROR"
DATABASE_ERROR = "DATABASE_ERROR"
RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
RERANKER_ERROR = "RERANKER_ERROR"
GENERATION_ERROR = "GENERATION_ERROR"
EVALUATION_ERROR = "EVALUATION_ERROR"
RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
READINESS_ERROR = "READINESS_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"

app = FastAPI(
    title="Pro RAG API",
    version="1.9.0",
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers_and_traceability(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", generate_request_id())
    request_id_var.set(req_id)
    endpoint_var.set(request.url.path)
    
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# =========================================================
# CONFIGURATION
# =========================================================

MAX_UPLOAD_SIZE = (
    20 * 1024 * 1024
)

MAX_FILENAME_LENGTH = 255

MAX_QUERY_LENGTH = 2000

MAX_HISTORY_LIMIT = 100

MAX_ANALYTICS_ROWS = 1000

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
}

ABSTENTION_MESSAGE = (
    "I don't have sufficient evidence "
    "in the knowledge base to answer that."
)

EVALUATION_TIMEOUT_SECONDS = 300

EVALUATION_REPORT_PATH = Path(
    "/app/tests/evaluation_report.json"
)


import threading

_models_ready = False

# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
def startup():

    init_db()

    def warmup_task():
        global _models_ready
        warmup_start = time.perf_counter()

        embedding_ready = False
        reranker_ready = False

        try:

            get_embedding_model()

            embedding_ready = True

        except Exception as exc:

            app_logger.info(
                f"[WARMUP EMBEDDING ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

        try:

            get_reranker()

            reranker_ready = True

        except Exception as exc:

            app_logger.info(
                f"[WARMUP RERANKER ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

        warmup_seconds = (
            time.perf_counter()
            - warmup_start
        )

        app_logger.info(
            "[WARMUP] "
            f"embedding={embedding_ready} "
            f"reranker={reranker_ready} "
            f"total={warmup_seconds:.2f}s"
        )
        
        if embedding_ready and reranker_ready:
            _models_ready = True

    threading.Thread(target=warmup_task, daemon=True).start()

# =========================================================
# REQUEST MODEL

# =========================================================



# =========================================================
# RATE LIMITING
# =========================================================

_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX_REQUESTS = 60

class SimpleRateLimiter:
    def __init__(self, max_requests: int, window: int):
        self.max_requests = max_requests
        self.window = window
        self.requests = {}

    def check(self, ip: str):
        now = time.monotonic()
        
        if ip not in self.requests:
            self.requests[ip] = []
            
        # Keep only requests within the window
        self.requests[ip] = [
            t for t in self.requests[ip]
            if now - t < self.window
        ]
        
        if len(self.requests[ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down."
            )
            
        self.requests[ip].append(now)

        # Basic memory bounds: prune old IPs occasionally
        if len(self.requests) > 10000:
            self.requests.clear()

query_limiter = SimpleRateLimiter(max_requests=_RATE_LIMIT_MAX_REQUESTS, window=_RATE_LIMIT_WINDOW)
ingest_limiter = SimpleRateLimiter(max_requests=10, window=_RATE_LIMIT_WINDOW)



# =========================================================
# HEALTH
# =========================================================

@app.get("/health", response_model=StatusResponse, summary="Liveness Probe", responses={200: {"model": StatusResponse}})
def health():
    return {"status": "alive"}

@app.get("/ready", response_model=StatusResponse, summary="Readiness Probe", responses={200: {"model": StatusResponse}, 503: {"model": ErrorResponse}})
def ready():
    if not _models_ready:
        raise APIError(503, READINESS_ERROR, "warming_up")
    
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            
        return {
            "status": "ready",
            "database": "ok",
        }
    except Exception as exc:
        app_logger.info(
            f"[READINESS ERROR] "
            f"{type(exc).__name__}: {exc}"
        )
        raise APIError(503, DATABASE_ERROR, "Database unavailable")


# =========================================================
# DOCUMENT INGESTION
# =========================================================

@app.post("/ingest", response_model=IngestResponse, summary="Ingest a Document", responses={200: {"model": IngestResponse}, 400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def ingest(
    request: Request,
    file: UploadFile = File(...),
):

    client_ip = request.client.host if request.client else "127.0.0.1"
    ingest_limiter.check(client_ip)

    # -----------------------------------------------------
    # Validate filename
    # -----------------------------------------------------

    raw_filename = file.filename or ""
    # Strip dangerous characters like null bytes and backslashes
    safe_filename = re.sub(r'[\x00\\]', '/', raw_filename)
    original_filename = Path(safe_filename).name.strip()
    
    # Restrict to strictly alphanumeric + safe chars
    original_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', original_filename)

    if not original_filename or original_filename == "_" or original_filename == ".":

        raise APIError(400, VALIDATION_ERROR, "Filename is required")

    if len(original_filename) > MAX_FILENAME_LENGTH:

        raise APIError(400, VALIDATION_ERROR, f"Filename is too long. Maximum length is {MAX_FILENAME_LENGTH} characters.")

    suffix = Path(
        original_filename
    ).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:

        raise APIError(400, VALIDATION_ERROR, "Only PDF, TXT and MD files are supported")

    # -----------------------------------------------------
    # Validate content type when provided
    #
    # Browsers are not authoritative here, so this is only
    # a secondary validation. Extension remains the primary
    # compatibility check.
    # -----------------------------------------------------

    declared_content_type = (
        file.content_type or ""
    ).lower()

    allowed_content_types = {
        ".pdf": {
            "application/pdf",
            "application/octet-stream",
        },
        ".txt": {
            "text/plain",
            "application/octet-stream",
        },
        ".md": {
            "text/markdown",
            "text/plain",
            "application/octet-stream",
        },
    }

    expected_types = (
        allowed_content_types.get(
            suffix,
            set(),
        )
    )

    if (
        declared_content_type
        and declared_content_type
        not in expected_types
    ):

        raise APIError(400, VALIDATION_ERROR, "File content type does not match the supported file extension.")

    temp_path = None
    total_size = 0

    try:

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as tmp:

            temp_path = Path(
                tmp.name
            )

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                total_size += len(
                    chunk
                )

                if (
                    total_size
                    > MAX_UPLOAD_SIZE
                ):

                    raise APIError(413, VALIDATION_ERROR, "File is too large. Maximum size is 20 MB.")

                tmp.write(chunk)

        if total_size == 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "The uploaded file "
                    "is empty"
                ),
            )

        # -------------------------------------------------
        # Index document
        # -------------------------------------------------

        try:
            document_id, chunk_count = (
                ingest_file(
                    temp_path,
                    original_filename,
                )
            )
        except ValueError as ve:
            raise HTTPException(
                status_code=400,
                detail=str(ve),
            )

        if (
            not document_id
            or chunk_count == 0
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "No readable text "
                    "was found in the document"
                ),
            )

        return {
            "status": "indexed",
            "document_id": document_id,
            "filename": original_filename,
            "chunks": chunk_count,
            "size_bytes": total_size,
        }

    except HTTPException:
        raise

    except Exception as exc:

        app_logger.info(
            f"[INGEST ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail="Document indexing failed",
        )

    finally:

        if temp_path:

            try:

                temp_path.unlink(
                    missing_ok=True
                )

            except Exception as exc:

                app_logger.info(
                    f"[TEMP CLEANUP ERROR] "
                    f"{type(exc).__name__}: {exc}"
                )


# =========================================================
# LIST DOCUMENTS
# =========================================================

@app.get("/documents", response_model=list[DocumentSchema], summary="List Documents")
def documents():

    try:

        with SessionLocal() as db:

            rows = (
                db.query(
                    Chunk.document_id,
                    Chunk.source,
                    func.count(
                        Chunk.id
                    ).label("chunks"),
                )
                .group_by(
                    Chunk.document_id,
                    Chunk.source,
                )
                .order_by(
                    Chunk.source.asc()
                )
                .limit(1000)
                .all()
            )

            return [
                {
                    "document_id":
                        row.document_id,

                    "filename":
                        row.source,

                    "chunks":
                        row.chunks,
                }
                for row in rows
            ]

    except Exception as exc:

        app_logger.info(
            f"[DOCUMENT LIST ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to load documents",
        )


# =========================================================
# DELETE DOCUMENT
# =========================================================

@app.delete(
    "/documents/{document_id}"
)
def delete_document(
    document_id: str,
):

    document_id = document_id.strip()

    if not document_id:

        raise HTTPException(
            status_code=400,
            detail="Document ID cannot be empty",
        )

    try:

        with SessionLocal() as db:

            deleted = (
                db.query(Chunk)
                .filter(
                    Chunk.document_id
                    == document_id
                )
                .delete(
                    synchronize_session=False
                )
            )

            db.commit()

        if deleted == 0:

            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        return {
            "status": "deleted",
            "document_id": document_id,
            "deleted_chunks": deleted,
        }

    except HTTPException:
        raise

    except Exception as exc:

        app_logger.info(
            f"[DELETE ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to delete document",
        )


# =========================================================
# QUERY HISTORY
# =========================================================

@app.get("/history", response_model=list[HistoryItemSchema], summary="Get Query History")
def history(
    limit: int = 20,
):

    limit = max(
        1,
        min(limit, MAX_HISTORY_LIMIT),
    )

    try:

        with SessionLocal() as db:

            rows = (
                db.query(QueryLog)
                .order_by(
                    QueryLog.created_at.desc()
                )
                .limit(limit)
                .all()
            )

            return [

                {
                    "id": row.id,

                    "question":
                        row.question,

                    "answer":
                        row.answer,

                    "confidence":
                        row.confidence,

                    "grounded":
                        bool(row.grounded),

                    "abstained":
                        bool(row.abstained),

                    "retrieved_chunks":
                        row.retrieved_chunks,

                    "cited_sources":
                        row.cited_sources,

                    "retrieval_ms":
                        row.retrieval_ms,

                    "generation_ms":
                        row.generation_ms,

                    "total_ms":
                        row.total_ms,

                    "citations":
                        row.citations_json
                        or [],

                    "evidence":
                        row.evidence_json
                        or [],

                    "created_at":
                        (
                            row.created_at.isoformat()
                            if row.created_at
                            else None
                        ),
                }

                for row in rows
            ]

    except Exception as exc:

        app_logger.info(
            f"[HISTORY ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load "
                "query history"
            ),
        )


# =========================================================
# CLEAR HISTORY
# =========================================================

@app.delete("/history", response_model=StatusResponse, summary="Clear History")
def clear_history():

    try:

        with SessionLocal() as db:

            deleted = (
                db.query(QueryLog)
                .delete(
                    synchronize_session=False
                )
            )

            db.commit()

        return {
            "status": "cleared",
            "deleted_records": deleted,
        }

    except Exception as exc:

        app_logger.info(
            f"[CLEAR HISTORY ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to clear "
                "query history"
            ),
        )


# =========================================================
# RAG ANALYTICS
# =========================================================

@app.get("/analytics", response_model=AnalyticsResponse, summary="Get Analytics")
def analytics():

    try:

        with SessionLocal() as db:

            rows = (
                db.query(QueryLog)
                .order_by(
                    QueryLog.created_at.desc()
                )
                .limit(MAX_ANALYTICS_ROWS)
                .all()
            )

            total_queries = len(
                rows
            )

            if total_queries == 0:

                return {
                    "total_queries": 0,
                    "grounded_queries": 0,
                    "abstained_queries": 0,
                    "citation_coverage": 0.0,
                    "grounded_rate": 0.0,
                    "abstention_rate": 0.0,
                    "average_latency_ms": 0.0,
                    "average_retrieval_ms": 0.0,
                    "average_generation_ms": 0.0,
                    "average_retrieved_chunks": 0.0,
                }

            grounded_queries = sum(
                1
                for row in rows
                if bool(row.grounded)
            )

            abstained_queries = sum(
                1
                for row in rows
                if bool(row.abstained)
            )

            queries_with_citations = sum(
                1
                for row in rows
                if row.cited_sources > 0
            )

            average_latency_ms = (
                sum(
                    row.total_ms or 0
                    for row in rows
                )
                / total_queries
            )

            average_retrieval_ms = (
                sum(
                    row.retrieval_ms or 0
                    for row in rows
                )
                / total_queries
            )

            average_generation_ms = (
                sum(
                    row.generation_ms or 0
                    for row in rows
                )
                / total_queries
            )

            average_retrieved_chunks = (
                sum(
                    row.retrieved_chunks or 0
                    for row in rows
                )
                / total_queries
            )

            return {

                "total_queries":
                    total_queries,

                "grounded_queries":
                    grounded_queries,

                "abstained_queries":
                    abstained_queries,

                "citation_coverage":
                    round(
                        (
                            queries_with_citations
                            / total_queries
                        ) * 100,
                        2,
                    ),

                "grounded_rate":
                    round(
                        (
                            grounded_queries
                            / total_queries
                        ) * 100,
                        2,
                    ),

                "abstention_rate":
                    round(
                        (
                            abstained_queries
                            / total_queries
                        ) * 100,
                        2,
                    ),

                "average_latency_ms":
                    round(
                        average_latency_ms,
                        2,
                    ),

                "average_retrieval_ms":
                    round(
                        average_retrieval_ms,
                        2,
                    ),

                "average_generation_ms":
                    round(
                        average_generation_ms,
                        2,
                    ),

                "average_retrieved_chunks":
                    round(
                        average_retrieved_chunks,
                        2,
                    ),
            }

    except Exception as exc:

        app_logger.info(
            f"[ANALYTICS ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load "
                "RAG analytics"
            ),
        )


# =========================================================
# EVALUATION
# =========================================================

@app.get("/evaluation", response_model=EvaluationResponse, summary="Run Evaluation")
def evaluation():

    evaluation_start = (
        time.perf_counter()
    )

    try:

        environment = os.environ.copy()

        environment[
            "PYTHONPATH"
        ] = "/app"

        environment[
            "PYTHONIOENCODING"
        ] = "utf-8"

        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "-q",
                "tests/test_rag.py",
            ],

            cwd="/app",

            env=environment,

            capture_output=True,

            text=True,

            encoding="utf-8",

            errors="replace",

            timeout=(
                EVALUATION_TIMEOUT_SECONDS
            ),
        )

        duration_seconds = (
            time.perf_counter()
            - evaluation_start
        )

        output = (
            result.stdout
            + "\n"
            + result.stderr
        ).strip()

        # -----------------------------------------------------
        # TEST COUNTS
        # -----------------------------------------------------

        passed = 0
        failed = 0
        skipped = 0

        passed_match = re.search(
            r"(\d+)\s+passed",
            output,
            re.IGNORECASE,
        )

        failed_match = re.search(
            r"(\d+)\s+failed",
            output,
            re.IGNORECASE,
        )

        skipped_match = re.search(
            r"(\d+)\s+skipped",
            output,
            re.IGNORECASE,
        )

        if passed_match:

            passed = int(
                passed_match.group(1)
            )

        if failed_match:

            failed = int(
                failed_match.group(1)
            )

        if skipped_match:

            skipped = int(
                skipped_match.group(1)
            )

        total_tests = (
            passed
            + failed
            + skipped
        )

        evaluation_status = (
            "passed"
            if result.returncode == 0
            else "failed"
        )

        # -----------------------------------------------------
        # MEASURED REPORT
        # -----------------------------------------------------

        metrics = {}

        report_available = (
            EVALUATION_REPORT_PATH
            .exists()
        )

        report_error = None

        report = {}

        if report_available:

            try:

                with (
                    EVALUATION_REPORT_PATH
                    .open(
                        "r",
                        encoding="utf-8",
                    )
                ) as report_file:

                    report = json.load(
                        report_file
                    )

                raw_metrics = (
                    report.get(
                        "metrics",
                        {}
                    )
                )

                metric_names = [
                    "recall_at_1",
                    "recall_at_k",
                    "mrr",
                    "citation_correctness",
                    "answer_grounding",
                    "abstention_accuracy",
                    "warm_latency_ms",
                ]

                # Important:
                # Do not use truthiness here because 0.0
                # is a valid measured metric value.
                metrics = {
                    name:
                        raw_metrics.get(
                            name
                        )
                    for name in metric_names
                    if raw_metrics.get(name)
                    is not None
                }

            except Exception as exc:

                report_error = (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                app_logger.info(
                    "[EVALUATION REPORT ERROR] "
                    f"{report_error}"
                )

        # -----------------------------------------------------
        # DATASET INFORMATION
        # -----------------------------------------------------

        dataset = report.get(
            "dataset",
            {}
        )

        benchmarks = report.get(
            "benchmarks",
            {}
        )

        overall_golden_success = (
            report.get(
                "overall_golden_success"
            )
        )

        return {

            "status":
                evaluation_status,

            "tests": {

                "passed":
                    passed,

                "failed":
                    failed,

                "skipped":
                    skipped,

                "total":
                    total_tests,
            },

            "dataset": dataset,

            "benchmarks": {

                "minimum_recall_at_1":
                    benchmarks.get(
                        "minimum_recall_at_1",
                        0.80,
                    ),

                "recall_k":
                    benchmarks.get(
                        "recall_k",
                        6,
                    ),

                "minimum_mrr":
                    benchmarks.get(
                        "minimum_mrr",
                        0.80,
                    ),

                "maximum_warm_latency_seconds":
                    benchmarks.get(
                        "maximum_warm_latency_seconds",
                        1.0,
                    ),
            },

            "metrics":
                metrics,

            "overall_golden_success":
                overall_golden_success,

            "report_available":
                report_available,

            "report_error":
                report_error,

            "duration_seconds":
                round(
                    duration_seconds,
                    2,
                ),

            "exit_code":
                result.returncode,

            "output":
                output[-5000:],
        }

    except subprocess.TimeoutExpired:

        raise HTTPException(
            status_code=504,
            detail=(
                "Evaluation timed out after "
                f"{EVALUATION_TIMEOUT_SECONDS} "
                "seconds"
            ),
        )

    except Exception as exc:

        app_logger.info(
            f"[EVALUATION ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        raise APIError(500, EVALUATION_ERROR, "Evaluation failed")


# =========================================================
# QUERY
# =========================================================

@app.post("/query", response_model=QueryResponse, summary="Query the Knowledge Base", responses={200: {"model": QueryResponse}, 400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
def query(
    request: Request,
    payload: QueryRequest,
):
    client_ip = request.client.host if request.client else "127.0.0.1"
    query_limiter.check(client_ip)

    if not _models_ready:
        raise APIError(503, READINESS_ERROR, "Models are warming up, please try again in a few seconds.")

    question = (
        payload.question.strip()
    )

    # -----------------------------------------------------
    # Validation
    # -----------------------------------------------------

    if not question:

        raise APIError(400, VALIDATION_ERROR, "Question cannot be empty")

    if not re.search(r"[A-Za-z0-9]", question):
        raise APIError(400, VALIDATION_ERROR, "Question must contain at least one alphanumeric character.")

    if len(question) > MAX_QUERY_LENGTH:

        raise APIError(422, VALIDATION_ERROR, f"Question is too long. Maximum length is {MAX_QUERY_LENGTH} characters.")

    request_start = (
        time.perf_counter()
    )

    try:

        # -------------------------------------------------
        # RETRIEVAL
        # -------------------------------------------------

        retrieval_start = (
            time.perf_counter()
        )

        evidence, retrieval_pipeline = (
            retrieve_with_diagnostics(
                question
            )
        )

        retrieval_ms = (
            time.perf_counter()
            - retrieval_start
        ) * 1000

        # -------------------------------------------------
        # GENERATION
        # -------------------------------------------------

        generation_start = (
            time.perf_counter()
        )

        result = answer(
            question,
            evidence,
        )

        generation_ms = (
            time.perf_counter()
            - generation_start
        ) * 1000

        # -------------------------------------------------
        # TOTAL LATENCY
        # -------------------------------------------------

        total_ms = (
            time.perf_counter()
            - request_start
        ) * 1000

        # -------------------------------------------------
        # BASIC DIAGNOSTICS
        # -------------------------------------------------

        retrieved_count = len(
            evidence
        )

        cited_count = len(
            result["citations"]
        )

        best_score = (
            max(
                float(score)
                for _, score in evidence
            )
            if evidence
            else None
        )

        answer_text = (
            result["answer"].strip()
        )

        abstained = (
            answer_text
            == ABSTENTION_MESSAGE
        )

        grounded = (
            not abstained
            and cited_count > 0
        )

        # -------------------------------------------------
        # SERIALIZE EVIDENCE
        # -------------------------------------------------

        evidence_records = [
            {
                "source":
                    chunk.source,

                "page":
                    chunk.page,

                "score":
                    float(score),

                "preview":
                    chunk.content[:500],
            }

            for chunk, score in evidence
        ]

        # -------------------------------------------------
        # PERSIST QUERY HISTORY
        #
        # Logging failure should not transform a successful
        # RAG answer into a failed query.
        # -------------------------------------------------

        try:

            with SessionLocal() as db:

                db.add(
                    QueryLog(

                        question=
                            question,

                        answer=
                            result["answer"],

                        confidence=
                            result["confidence"],

                        grounded=
                            1 if grounded
                            else 0,

                        abstained=
                            1 if abstained
                            else 0,

                        retrieved_chunks=
                            retrieved_count,

                        cited_sources=
                            cited_count,

                        retrieval_ms=
                            int(
                                round(
                                    retrieval_ms
                                )
                            ),

                        generation_ms=
                            int(
                                round(
                                    generation_ms
                                )
                            ),

                        total_ms=
                            int(
                                round(
                                    total_ms
                                )
                            ),

                        citations_json=
                            result["citations"],

                        evidence_json=
                            evidence_records,
                    )
                )

                db.commit()

        except Exception as exc:

            app_logger.info(
                f"[QUERY LOGGING ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return {

            "question":
                question,

            "answer":
                result["answer"],

            "confidence":
                result["confidence"],

            "citations":
                result["citations"],

            "diagnostics": {

                "retrieved_chunks":
                    retrieved_count,

                "cited_sources":
                    cited_count,

                "best_retrieval_score":
                    (
                        round(
                            best_score,
                            4
                        )
                        if best_score
                        is not None
                        else None
                    ),

                "retrieval_ms":
                    round(
                        retrieval_ms,
                        2,
                    ),

                "generation_ms":
                    round(
                        generation_ms,
                        2,
                    ),

                "total_ms":
                    round(
                        total_ms,
                        2,
                    ),

                "grounded":
                    grounded,

                "abstained":
                    abstained,

                "retrieval_pipeline":
                    retrieval_pipeline,
            },

            "retrieved":
                evidence_records,
        }

    except HTTPException:
        raise

    except Exception as exc:

        app_logger.info(
            f"[QUERY ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        raise APIError(500, INTERNAL_ERROR, "Query processing failed")


