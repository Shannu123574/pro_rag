import pytest
pytestmark = pytest.mark.scale

import pytest
from tests.dataset import EVAL_DATASET
from app.retrieval import (
    dense_search,
    lexical_search,
    rrf,
    get_reranker,
    retrieve
)
from app.config import settings

def _check_recall_1(results, expected_source):
    if not results:
        return 0
    first = results[0]
    if isinstance(first, dict):
        source = first.get("source") or first.get("metadata", {}).get("filename")
    else:
        source = getattr(first, "source", None)
    return 1 if source == expected_source else 0

def test_ablations():
    dense_hits = 0
    lexical_hits = 0
    hybrid_hits = 0
    full_hits = 0
    total = len(EVAL_DATASET)

    for case in EVAL_DATASET:
        question = case["question"]
        expected_source = case["expected_source"]

        # 1. Dense Only
        dense_results = dense_search(question)[0]
        dense_hits += _check_recall_1(dense_results, expected_source)

        # 2. Lexical Only
        lexical_results = lexical_search(question)[0] if isinstance(lexical_search(question), tuple) else lexical_search(question)
        if isinstance(lexical_results, tuple): lexical_results = lexical_results[0]
        lexical_hits += _check_recall_1(lexical_results, expected_source)

        # 3. Hybrid (Dense + Lexical + RRF, no rerank)
        fused = rrf(dense_results, lexical_results)
        hybrid_hits += _check_recall_1(fused[:6], expected_source)

        # 4. Full Pipeline
        fused_full = rrf(dense_results, lexical_results)
        
        # Rerank
        if fused_full:
            reranker = get_reranker()
            pairs = [[question, getattr(chunk, "content", "")] for chunk in fused_full]
            scores = reranker.predict(pairs)
            for i, score in enumerate(scores):
                setattr(fused_full[i], "score", float(score))
            
            fused_full.sort(key=lambda x: getattr(x, "score", 0), reverse=True)
            
        full_hits += _check_recall_1(fused_full[:6], expected_source)

    print("\nRetrieval Ablations (Recall@1):")
    print(f"Dense Only:     {dense_hits/total*100:.1f}%")
    print(f"Lexical Only:   {lexical_hits/total*100:.1f}%")
    print(f"Hybrid Fusion:  {hybrid_hits/total*100:.1f}%")
    print(f"Full Pipeline:  {full_hits/total*100:.1f}%")
    
    # Reranker should be strictly better or equal
    assert full_hits >= hybrid_hits
