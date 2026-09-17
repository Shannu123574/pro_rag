import pytest
pytestmark = pytest.mark.scale

import pytest
import time
from sqlalchemy import text
from app.db import SessionLocal, engine, Chunk
from app.main import app as fastapi_app, ingest_limiter, query_limiter
from fastapi.testclient import TestClient

def test_scale_latency(monkeypatch):
    """
    Test latency with 50 synthetic documents.
    """
    # Disable rate limits for this test
    monkeypatch.setattr(ingest_limiter, "check", lambda ip: None)
    monkeypatch.setattr(query_limiter, "check", lambda ip: None)
    
    with TestClient(fastapi_app) as client:
        # Wait for models to warm up
        for _ in range(30):
            res = client.get("/ready")
            if res.status_code == 200:
                break
            time.sleep(1)
            
        # Generate 50 dummy markdown documents
        start_ingest = time.perf_counter()
        
        for i in range(50):
            content = f"# Scale Document {i}\n\n"
            for j in range(20):
                content += f"This is paragraph {j} of scale document {i}. " * 5 + "\n\n"
            
            for _ in range(5):
                res = client.post("/ingest", files={"file": (f"scale_doc_{i}.md", content, "text/markdown")})
                if res.status_code != 503:
                    break
                time.sleep(2)
            assert res.status_code == 200, res.text
            
        ingest_time = time.perf_counter() - start_ingest
        print(f"Ingested 50 documents in {ingest_time:.2f} seconds.")
        
        # Now run queries
        queries = [
            "What is scale document 10 about?",
            "Can you tell me about paragraph 5 in document 20?",
            "What does document 30 say?",
            "Tell me about document 40 paragraph 10.",
            "Scale document 49 summary."
        ] * 4 # 20 queries total
        
        latencies = []
        for q in queries:
            start = time.perf_counter()
            # Retry on 503 (models warming up)
            for _ in range(5):
                res = client.post("/query", json={"question": q})
                if res.status_code != 503:
                    break
                time.sleep(2)
            latencies.append(time.perf_counter() - start)
            assert res.status_code == 200
            
        latencies.sort()
        p50 = latencies[len(latencies)//2]
        p90 = latencies[int(len(latencies)*0.9)]
        p95 = latencies[int(len(latencies)*0.95)]
        max_lat = latencies[-1]
        
        print(f"Query Latencies (N={len(latencies)}):")
        print(f"P50: {p50*1000:.2f} ms")
        print(f"P90: {p90*1000:.2f} ms")
        print(f"P95: {p95*1000:.2f} ms")
        print(f"Max: {max_lat*1000:.2f} ms")
        
        assert p90 < 10.0, f"P90 latency exceeded 10.0 seconds (was {p90:.2f}s)"

def test_hnsw_index_usage():
    """
    Run EXPLAIN ANALYZE to verify HNSW is used for dense search.
    """
    with SessionLocal() as db:
        # Get one vector to search with
        chunk = db.query(Chunk).first()
        if not chunk:
            pytest.skip("No chunks in db")
            
        vector_str = "[" + ",".join(str(x) for x in chunk.embedding) + "]"
        
        # Disable seq scan to force index scan
        db.execute(text("SET enable_seqscan = off;"))
        
        # Run EXPLAIN ANALYZE
        query = f"EXPLAIN ANALYZE SELECT id FROM chunks ORDER BY embedding <=> '{vector_str}' LIMIT 12;"
        result = db.execute(text(query)).fetchall()
        
        explain_output = "\n".join(row[0] for row in result)
        print("EXPLAIN output:")
        print(explain_output)
        
        # Check if Index Scan or hnsw is in the output
        assert "Index Scan" in explain_output, "HNSW index was not used for dense search!"

