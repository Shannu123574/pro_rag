import pytest
import os
from fastapi.testclient import TestClient
from app.main import app
from tests.dataset import EVAL_DATASET

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_eval_corpus():
    """Ingest the eval fixtures before running tests."""
    # Wait for ready
    import time
    with TestClient(app) as client:
        ready = False
        for _ in range(60):
            if client.get("/ready").status_code == 200:
                ready = True
                break
            time.sleep(1)
        assert ready, "API did not become ready"

        fixtures_dir = "tests/fixtures/eval"
        if not os.path.exists(fixtures_dir):
            return

        for filename in os.listdir(fixtures_dir):
            if filename.endswith(".md"):
                with open(os.path.join(fixtures_dir, filename), "rb") as f:
                    content = f.read()
                    client.post("/ingest", files={"file": (filename, content, "text/markdown")})

def get_case_result(question: str):
    with TestClient(app) as client:
        res = client.post("/query", json={"question": question})
        assert res.status_code == 200, res.text
        return res.json()

def test_chunk_level_recall_at_1():
    hits = 0
    total = 0
    for case in EVAL_DATASET:
        if case["expected_chunk_text"]:
            total += 1
            result = get_case_result(case["question"])
            top_chunk_text = result["retrieved"][0]["preview"] if result["retrieved"] else ""
            if case["expected_chunk_text"] in top_chunk_text:
                hits += 1
    
    recall = hits / total if total else 0
    assert recall >= 0.8, f"Chunk Recall@1 is {recall:.2%}"

def test_chunk_level_recall_at_k():
    hits = 0
    total = 0
    for case in EVAL_DATASET:
        if case["expected_chunk_text"]:
            total += 1
            result = get_case_result(case["question"])
            texts = [r["preview"] for r in result["retrieved"][:6]]
            if any(case["expected_chunk_text"] in text for text in texts):
                hits += 1
    
    recall = hits / total if total else 0
    assert recall >= 0.8, f"Chunk Recall@6 is {recall:.2%}"

def test_answer_faithfulness():
    failures = []
    for case in EVAL_DATASET:
        result = get_case_result(case["question"])
        ans_lower = result["answer"].lower()
        
        # Test required concepts
        for concept in case["required_concepts"]:
            if concept.lower() not in ans_lower:
                failures.append(f"Q: {case['question']} missing concept: {concept}")
        
        # Test forbidden concepts
        for concept in case["forbidden_concepts"]:
            if concept.lower() in ans_lower:
                failures.append(f"Q: {case['question']} included forbidden concept: {concept}")
                
        # Test abstention
        if case["should_abstain"]:
            if not result["diagnostics"]["abstained"]:
                failures.append(f"Q: {case['question']} failed to abstain.")
        else:
            if result["diagnostics"]["abstained"]:
                failures.append(f"Q: {case['question']} erroneously abstained.")

    assert not failures, "\n".join(failures)

def test_citation_faithfulness():
    # Only tests if every citation given actually maps to a retrieved chunk 
    # that has the required concepts (if the question has required concepts).
    failures = []
    for case in EVAL_DATASET:
        if case["should_abstain"] or not case["required_concepts"]:
            continue
        
        result = get_case_result(case["question"])
        
        # Map citations to chunks
        citations = result["citations"]
        if not citations:
            failures.append(f"Q: {case['question']} had no citations.")
            continue
            
        for citation in citations:
            # Map citation ID (e.g. S1) to retrieved index (0-indexed)
            try:
                idx = int(citation["id"].replace("S", "")) - 1
                chunk_text = result["retrieved"][idx]["preview"]
            except (ValueError, IndexError, KeyError):
                chunk_text = ""
            
            # The cited text MUST support at least one required concept 
            # (or the answer as a whole is grounded).
            supports = any(concept.lower() in chunk_text.lower() for concept in case["required_concepts"])
            if not supports:
                failures.append(f"Q: {case['question']} cited irrelevant chunk: {chunk_text[:50]}")

    assert not failures, "\n".join(failures)

def test_answer_consistency():
    # Run the first supported case 5 times
    case = next(c for c in EVAL_DATASET if not c["should_abstain"])
    
    results = [get_case_result(case["question"]) for _ in range(3)]
    
    # Answers should be identical for deterministic RAG paths, but might vary slightly for LLM.
    # We at least enforce citations and abstention stay identical.
    first_citations = [c["id"] for c in results[0]["citations"]]
    
    for i in range(1, 3):
        assert results[i]["diagnostics"]["abstained"] == results[0]["diagnostics"]["abstained"]
        assert [c["id"] for c in results[i]["citations"]] == first_citations
