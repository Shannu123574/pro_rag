from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class StatusResponse(BaseModel):
    status: str
    database: Optional[str] = None

class ErrorDetail(BaseModel):
    code: str
    message: str

class ErrorResponse(BaseModel):
    detail: ErrorDetail

class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

class CitationSchema(BaseModel):
    id: str
    source: str
    page: Optional[int] = None
    score: Optional[float] = None
    text: Optional[str] = None
    evidence_support: Optional[str] = None

class DenseDiagnostics(BaseModel):
    count: int
    latency_ms: float
    embedding_latency_ms: float
    vector_db_latency_ms: float

class LexicalDiagnostics(BaseModel):
    count: int
    latency_ms: float

class RRFDiagnostics(BaseModel):
    count: int
    latency_ms: float

class RerankDiagnostics(BaseModel):
    candidate_count: int
    returned_count: int
    latency_ms: float

class RetrievalPipelineDiagnostics(BaseModel):
    dense: DenseDiagnostics
    lexical: LexicalDiagnostics
    rrf: RRFDiagnostics
    rerank: RerankDiagnostics
    total_latency_ms: float
    candidate_multiplier: int
    stages: List[Dict[str, Any]]

class GenerationDiagnostics(BaseModel):
    latency_ms: float
    deterministic_fast_path: bool
    llm_fallback: bool

class DiagnosticsSchema(BaseModel):
    retrieved_chunks: int
    cited_sources: int
    best_retrieval_score: Optional[float]
    retrieval_ms: float
    generation_ms: float
    generation: Optional[GenerationDiagnostics] = None
    total_ms: float
    grounded: bool
    abstained: bool
    retrieval_pipeline: RetrievalPipelineDiagnostics

class QueryResponse(BaseModel):
    question: str
    answer: str
    confidence: str
    citations: List[CitationSchema]
    diagnostics: DiagnosticsSchema
    retrieved: List[Dict[str, Any]]

class IngestResponse(BaseModel):
    status: str
    document_id: str
    filename: str
    chunks: int
    size_bytes: int

class DocumentSchema(BaseModel):
    document_id: str
    filename: str
    chunks: int
    created_at: Optional[str] = None

class HistoryItemSchema(BaseModel):
    id: int
    created_at: str
    question: str
    answer: str
    confidence: str
    citations: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    abstained: bool
    grounded: bool
    retrieved_chunks: Optional[int] = None
    cited_sources: Optional[int] = None
    retrieval_ms: Optional[float] = None
    generation_ms: Optional[float] = None
    total_ms: Optional[float] = None

class AnalyticsResponse(BaseModel):
    total_queries: int
    grounded_queries: int
    abstained_queries: int
    citation_coverage: float
    grounded_rate: float
    abstention_rate: float
    average_latency_ms: float
    average_retrieval_ms: float
    average_generation_ms: float
    average_retrieved_chunks: float

class QualityScores(BaseModel):
    recall_at_1: Optional[float]
    recall_at_6: Optional[float]
    mrr: Optional[float]
    citation_correctness: Optional[float]
    grounding: Optional[float]
    abstention: Optional[float]

class EvaluationResponse(BaseModel):
    status: str
    total_samples: int
    quality_scores: QualityScores
    avg_latency_ms: Optional[float]
    p90_latency_ms: Optional[float]
    report_available: bool
