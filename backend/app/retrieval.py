import re
import time

from sqlalchemy import select, text
from sentence_transformers import SentenceTransformer, CrossEncoder

from app.config import settings
from app.db import SessionLocal, Chunk
from app.logger import setup_logger

logger = setup_logger("retrieval")


import threading

_embedding_model = None
_reranker = None
_model_lock = threading.Lock()


# ============================================================
# MODELS
# ============================================================

def get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        with _model_lock:
            if _embedding_model is None:
                _embedding_model = SentenceTransformer(
                    "sentence-transformers/all-MiniLM-L6-v2"
                )

    return _embedding_model


def get_reranker():
    global _reranker

    if _reranker is None:
        with _model_lock:
            if _reranker is None:
                _reranker = CrossEncoder(
                    "cross-encoder/ms-marco-MiniLM-L-6-v2",
                    device="cpu",
                    trust_remote_code=False,
                    model_kwargs={
                        "low_cpu_mem_usage": False
                    }
                )

    return _reranker


# ============================================================
# QUERY EXPANSION
# ============================================================

def _expand_retrieval_query(query):
    """
    Add domain-relevant retrieval terms for specific question
    patterns where the user's wording differs from the wording
    used in the knowledge base.

    The original query is always preserved.

    This is intentionally targeted rather than a general-purpose
    query rewriting system so unrelated queries remain unchanged.
    """

    question_lower = query.lower()

    expanded_terms = []

    # --------------------------------------------------------
    # Causal dawn / early-morning questions
    # --------------------------------------------------------
    #
    # User wording:
    #
    #   "Why should shrimp ponds be checked around dawn?"
    #
    # Knowledge-base wording:
    #
    #   "early morning"
    #   "overnight respiration"
    #   "dissolved oxygen"
    #   "morning monitoring is important"
    #
    # Add those concepts so both dense and lexical retrieval
    # can connect the question to the correct evidence.
    # --------------------------------------------------------

    is_causal_question = (
        "why" in question_lower
        or "reason" in question_lower
        or "important" in question_lower
    )

    is_morning_question = (
        "dawn" in question_lower
        or "early morning" in question_lower
        or "morning" in question_lower
    )

    if (
        is_causal_question
        and is_morning_question
    ):
        expanded_terms.extend([
            "early morning",
            "overnight respiration",
            "dissolved oxygen",
            "morning monitoring",
            "oxygen low",
        ])

    if not expanded_terms:
        return query

    return (
        f"{query} "
        + " ".join(expanded_terms)
    )


# ============================================================
# DENSE SEARCH
# ============================================================

def dense_search(query):
    start = time.perf_counter()

    model = get_embedding_model()

    embedding_start = time.perf_counter()

    q = model.encode(
        query,
        normalize_embeddings=True
    ).tolist()

    embedding_time = (
        time.perf_counter()
        - embedding_start
    )

    db_start = time.perf_counter()

    with SessionLocal() as db:
        results = db.execute(
            select(Chunk)
            .order_by(
                Chunk.embedding.cosine_distance(q)
            )
            .limit(settings.top_k_dense)
        ).scalars().all()

    db_time = (
        time.perf_counter()
        - db_start
    )

    total_time = (
        time.perf_counter()
        - start
    )

    logger.info(
        f"[PROFILE] DENSE "
        f"embedding={embedding_time:.4f}s "
        f"db={db_time:.4f}s "
        f"total={total_time:.4f}s "
        f"results={len(results)}"
    )

    return results, embedding_time, db_time


# ============================================================
# LEXICAL SEARCH
# ============================================================

def _build_lexical_or_query(query):
    """
    Build a safe PostgreSQL tsquery using OR semantics.

    Example:

        "How often is Pond 7 checked?"

    becomes approximately:

        "how | often | is | pond | 7 | checked"

    PostgreSQL's English text-search configuration removes
    stop-words and normalizes terms during to_tsquery().
    Only alphanumeric tokens are retained here so raw user
    input cannot inject tsquery operators.
    """

    tokens = re.findall(
        r"[A-Za-z0-9]+",
        query.lower()
    )

    # Remove duplicate terms while preserving order.
    unique_tokens = list(
        dict.fromkeys(tokens)
    )

    if not unique_tokens:
        return None

    return " | ".join(unique_tokens)


def lexical_search(query):
    start = time.perf_counter()

    # --------------------------------------------------------
    # FIRST PASS
    # --------------------------------------------------------

    primary_sql = text("""
        SELECT id
        FROM chunks
        WHERE to_tsvector(
                  'english',
                  content
              )
              @@ websearch_to_tsquery(
                  'english',
                  :q
              )

        ORDER BY ts_rank_cd(
            to_tsvector(
                'english',
                content
            ),
            websearch_to_tsquery(
                'english',
                :q
            )
        ) DESC

        LIMIT :k
    """)

    with SessionLocal() as db:

        ids = [
            row[0]
            for row in db.execute(
                primary_sql,
                {
                    "q": query,
                    "k": settings.top_k_lexical,
                }
            ).all()
        ]

        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        if not ids:

            fallback_query = _build_lexical_or_query(
                query
            )

            if fallback_query:

                fallback_sql = text("""
                    SELECT id
                    FROM chunks
                    WHERE to_tsvector(
                              'english',
                              content
                          )
                          @@ to_tsquery(
                              'english',
                              :tsq
                          )

                    ORDER BY ts_rank_cd(
                        to_tsvector(
                            'english',
                            content
                        ),
                        to_tsquery(
                            'english',
                            :tsq
                        )
                    ) DESC

                    LIMIT :k
                """)

                ids = [
                    row[0]
                    for row in db.execute(
                        fallback_sql,
                        {
                            "tsq": fallback_query,
                            "k": settings.top_k_lexical,
                        }
                    ).all()
                ]

        # ----------------------------------------------------
        # LOAD ORM OBJECTS IN SEARCH ORDER
        # ----------------------------------------------------

        if not ids:

            elapsed = (
                time.perf_counter()
                - start
            )

            logger.info(
                f"[PROFILE] LEXICAL "
                f"total={elapsed:.4f}s "
                f"results=0"
            )

            return []

        rows = (
            db.query(Chunk)
            .filter(
                Chunk.id.in_(ids)
            )
            .all()
        )

        by_id = {
            row.id: row
            for row in rows
        }

        results = [
            by_id[item_id]
            for item_id in ids
            if item_id in by_id
        ]

    elapsed = (
        time.perf_counter()
        - start
    )

    logger.info(
        f"[PROFILE] LEXICAL "
        f"total={elapsed:.4f}s "
        f"results={len(results)}"
    )

    return results


# ============================================================
# RECIPROCAL RANK FUSION
# ============================================================

def rrf(dense, lexical, k=60):
    start = time.perf_counter()

    scores = {}
    objects = {}

    for rank, item in enumerate(dense):

        scores[item.id] = (
            scores.get(item.id, 0)
            + (
                1 /
                (k + rank + 1)
            )
        )

        objects[item.id] = item

    for rank, item in enumerate(lexical):

        scores[item.id] = (
            scores.get(item.id, 0)
            + (
                1 /
                (k + rank + 1)
            )
        )

        objects[item.id] = item

    result = [
        objects[item_id]
        for item_id in sorted(
            scores,
            key=scores.get,
            reverse=True
        )
    ]

    elapsed = (
        time.perf_counter()
        - start
    )

    logger.info(
        f"[PROFILE] RRF "
        f"total={elapsed:.4f}s "
        f"candidates={len(result)}"
    )

    return result


# ============================================================
# NORMAL RETRIEVAL
# ============================================================

def retrieve(query):
    total_start = time.perf_counter()

    retrieval_query = _expand_retrieval_query(
        query
    )

    if retrieval_query != query:
        logger.info(
            f"[QUERY EXPANSION] "
            f"original={query!r}"
        )
        logger.info(
            f"[QUERY EXPANSION] "
            f"expanded={retrieval_query!r}"
        )

    dense_start = time.perf_counter()

    dense, _, _ = dense_search(
        retrieval_query
    )

    dense_wrapper_time = (
        time.perf_counter()
        - dense_start
    )

    lexical_start = time.perf_counter()

    lexical = lexical_search(
        retrieval_query
    )

    lexical_wrapper_time = (
        time.perf_counter()
        - lexical_start
    )

    fused = rrf(
        dense,
        lexical
    )

    if not fused:

        total_time = (
            time.perf_counter()
            - total_start
        )

        logger.info(
            f"[PROFILE] RETRIEVE "
            f"total={total_time:.4f}s "
            f"rerank=0s"
        )

        return []

    candidate_limit = max(
        settings.top_k_rerank
        * settings.rerank_candidate_multiplier,
        8
    )

    candidates = fused[
        :candidate_limit
    ]

    # --------------------------------------------------------
    # RERANK
    #
    # Use the expanded retrieval query here as well so that
    # the CrossEncoder sees the same causal concepts that
    # improved candidate retrieval.
    # --------------------------------------------------------

    rerank_start = time.perf_counter()

    reranker = get_reranker()

    rerank_scores = reranker.predict(
        [
            (
                retrieval_query,
                chunk.content
            )
            for chunk in candidates
        ]
    )

    ranked = sorted(
        zip(
            candidates,
            rerank_scores
        ),
        key=lambda pair:
            float(pair[1]),
        reverse=True
    )

    selected = []

    for chunk, score in ranked:

        if (
            len(selected)
            >= settings.top_k_rerank
        ):
            break

        selected.append(
            (
                chunk,
                float(score)
            )
        )

    rerank_time = (
        time.perf_counter()
        - rerank_start
    )

    total_time = (
        time.perf_counter()
        - total_start
    )

    logger.info(
        f"[PROFILE] RERANK "
        f"total={rerank_time:.4f}s "
        f"candidates={len(candidates)}"
    )

    logger.info(
        f"[PROFILE] RETRIEVE TOTAL "
        f"dense={dense_wrapper_time:.4f}s "
        f"lexical={lexical_wrapper_time:.4f}s "
        f"rerank={rerank_time:.4f}s "
        f"total={total_time:.4f}s"
    )

    return selected


# ============================================================
# EXPLAINABLE RETRIEVAL
# ============================================================

def retrieve_with_diagnostics(query):
    """
    Run the full hybrid retrieval pipeline and expose
    how each stage affected the final ranking.

    Pipeline:

        Query Expansion
             ↓
        Dense Search
             ↓
        Lexical Search
             ↓
        RRF Fusion
             ↓
        Candidate Selection
             ↓
        Cross-Encoder Reranking
             ↓
        Final Evidence
    """

    total_start = time.perf_counter()

    retrieval_query = _expand_retrieval_query(
        query
    )

    if retrieval_query != query:
        logger.info(
            f"[QUERY EXPANSION] "
            f"original={query!r}"
        )
        logger.info(
            f"[QUERY EXPANSION] "
            f"expanded={retrieval_query!r}"
        )

    # --------------------------------------------------------
    # DENSE
    # --------------------------------------------------------

    dense_start = time.perf_counter()

    dense, embedding_time, db_time = dense_search(
        retrieval_query
    )

    dense_time = (
        time.perf_counter()
        - dense_start
    )

    dense_rank = {
        chunk.id: rank + 1
        for rank, chunk in enumerate(dense)
    }

    # --------------------------------------------------------
    # LEXICAL
    # --------------------------------------------------------

    lexical_start = time.perf_counter()

    lexical = lexical_search(
        retrieval_query
    )

    lexical_time = (
        time.perf_counter()
        - lexical_start
    )

    lexical_rank = {
        chunk.id: rank + 1
        for rank, chunk in enumerate(lexical)
    }

    # --------------------------------------------------------
    # RRF
    # --------------------------------------------------------

    rrf_start = time.perf_counter()

    fused = rrf(
        dense,
        lexical
    )

    rrf_time = (
        time.perf_counter()
        - rrf_start
    )

    rrf_rank = {
        chunk.id: rank + 1
        for rank, chunk in enumerate(fused)
    }

    # --------------------------------------------------------
    # EMPTY RETRIEVAL
    # --------------------------------------------------------

    if not fused:

        total_time = (
            time.perf_counter()
            - total_start
        )

        diagnostics = {
            "dense": {
                "count": len(dense),
                "latency_ms": round(
                    dense_time * 1000,
                    2
                ),
            },

            "lexical": {
                "count": len(lexical),
                "latency_ms": round(
                    lexical_time * 1000,
                    2
                ),
            },

            "rrf": {
                "count": 0,
                "latency_ms": round(
                    rrf_time * 1000,
                    2
                ),
            },

            "rerank": {
                "candidate_count": 0,
                "returned_count": 0,
                "latency_ms": 0.0,
            },

            "total_latency_ms": round(
                total_time * 1000,
                2
            ),

            "candidate_multiplier": (
                settings.rerank_candidate_multiplier
            ),

            "stages": [],
        }

        return [], diagnostics

    # --------------------------------------------------------
    # CANDIDATES
    # --------------------------------------------------------

    candidate_limit = max(
        settings.top_k_rerank
        * settings.rerank_candidate_multiplier,
        8
    )

    candidates = fused[
        :candidate_limit
    ]

    candidate_ids = {
        chunk.id
        for chunk in candidates
    }

    # --------------------------------------------------------
    # CROSS ENCODER
    # --------------------------------------------------------

    rerank_start = time.perf_counter()

    reranker = get_reranker()

    rerank_scores = reranker.predict(
        [
            (
                retrieval_query,
                chunk.content
            )
            for chunk in candidates
        ]
    )

    ranked = sorted(
        zip(
            candidates,
            rerank_scores
        ),
        key=lambda pair:
            float(pair[1]),
        reverse=True
    )

    selected = []

    for chunk, score in ranked:

        if (
            len(selected)
            >= settings.top_k_rerank
        ):
            break

        selected.append(
            (
                chunk,
                float(score)
            )
        )

    rerank_time = (
        time.perf_counter()
        - rerank_start
    )

    # --------------------------------------------------------
    # EXPLAIN EACH FINAL RESULT
    # --------------------------------------------------------

    stages = []

    for final_rank, (
        chunk,
        score
    ) in enumerate(
        selected,
        start=1
    ):

        stages.append(
            {
                "chunk_id": chunk.id,

                "source": chunk.source,

                "page": chunk.page,

                "final_rank": final_rank,

                "dense_rank": dense_rank.get(
                    chunk.id
                ),

                "lexical_rank": lexical_rank.get(
                    chunk.id
                ),

                "rrf_rank": rrf_rank.get(
                    chunk.id
                ),

                "candidate": (
                    chunk.id
                    in candidate_ids
                ),

                "rerank_score": round(
                    float(score),
                    6
                ),
            }
        )

    total_time = (
        time.perf_counter()
        - total_start
    )

    # --------------------------------------------------------
    # LOGGING
    # --------------------------------------------------------

    logger.info(
        f"[PROFILE] "
        f"EXPLAINABLE RETRIEVE "
        f"dense={dense_time:.4f}s "
        f"lexical={lexical_time:.4f}s "
        f"rrf={rrf_time:.4f}s "
        f"rerank={rerank_time:.4f}s "
        f"total={total_time:.4f}s "
        f"results={len(selected)}"
    )

    logger.info(
        f"[PIPELINE] "
        f"dense={len(dense)} "
        f"lexical={len(lexical)} "
        f"rrf={len(fused)} "
        f"candidates={len(candidates)} "
        f"final={len(selected)}"
    )

    # --------------------------------------------------------
    # DIAGNOSTICS OBJECT
    # --------------------------------------------------------

    diagnostics = {
        "dense": {
            "count": len(dense),
            "latency_ms": round(
                dense_time * 1000,
                2
            ),
            "embedding_latency_ms": round(embedding_time * 1000, 2),
            "vector_db_latency_ms": round(db_time * 1000, 2),
        },

        "lexical": {
            "count": len(lexical),
            "latency_ms": round(
                lexical_time * 1000,
                2
            ),
        },

        "rrf": {
            "count": len(fused),
            "latency_ms": round(
                rrf_time * 1000,
                2
            ),
        },

        "rerank": {
            "candidate_count": len(
                candidates
            ),

            "returned_count": len(
                selected
            ),

            "latency_ms": round(
                rerank_time * 1000,
                2
            ),
        },

        "total_latency_ms": round(
            total_time * 1000,
            2
        ),

        "candidate_multiplier": (
            settings.rerank_candidate_multiplier
        ),

        "stages": stages,
    }

    return selected, diagnostics
