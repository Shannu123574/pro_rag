import pytest
pytestmark = pytest.mark.scale

import pytest
from app.db import SessionLocal, Chunk

def test_corpus_quality_audit():
    with SessionLocal() as db:
        chunks = db.query(Chunk).all()
        if not chunks:
            pytest.skip("Database is empty")

        sizes = [len(c.content.split()) for c in chunks]
        max_size = max(sizes)
        min_size = min(sizes)
        avg_size = sum(sizes) / len(sizes)

        print(f"\nCorpus Quality Audit:")
        print(f"Total Chunks: {len(chunks)}")
        print(f"Max Chunk Size (words): {max_size}")
        print(f"Min Chunk Size (words): {min_size}")
        print(f"Avg Chunk Size (words): {avg_size:.2f}")

        assert max_size < 1500, f"Found suspiciously large chunk of {max_size} words."

def test_edge_case_abstention():
    from app.generation import answer
    prompt = "What is the airspeed velocity of an unladen swallow?"
    ans = answer(prompt, [])
    ans_text = ans.get("answer", "")
    ans_lower = ans_text.lower()
    assert "sufficient evidence" in ans_lower or "knowledge base" in ans_lower
    print("\nEdge Case Test (Out of domain): PASSED - Model correctly abstained.")

