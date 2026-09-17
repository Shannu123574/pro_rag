import time
from fastapi.testclient import TestClient
from app.main import app

def test_true_e2e_lifecycle():
    with TestClient(app) as client:
        # 1. Wait for ready
        ready = False
        for _ in range(30):
            res = client.get("/ready")
            if res.status_code == 200:
                ready = True
                break
            time.sleep(1)
        
        assert ready, "API did not become ready"

        # 2. Upload a test document
        doc_content = "Pond 7 is checked twice daily. Extra e2e data."
        files = {
            "file": ("e2e_secret.txt", doc_content, "text/plain")
        }
        res = client.post("/ingest", files=files)
        assert res.status_code == 200, res.text
        doc_id = res.json()["document_id"]

        # 3. Verify it is listed in /documents
        res = client.get("/documents")
        assert res.status_code == 200
        docs = res.json()
        assert any(d["document_id"] == doc_id for d in docs)

        # 4. Query the document
        res = client.post("/query", json={"question": "How often is Pond 7 checked?"})
        assert res.status_code == 200
        query_result = res.json()
        
        assert "twice daily" in query_result["answer"]
        assert query_result["diagnostics"]["grounded"] is True
        assert len(query_result["citations"]) > 0

        # 5. Verify it's in /history
        res = client.get("/history")
        assert res.status_code == 200
        history = res.json()
        assert any("twice daily" in h["answer"] for h in history)

        # 6. Delete document
        res = client.delete(f"/documents/{doc_id}")
        assert res.status_code == 200

        # 7. Verify removed from /documents
        res = client.get("/documents")
        assert res.status_code == 200
        docs = res.json()
        assert not any(d["document_id"] == doc_id for d in docs)

        # 8. Query again, expect abstention
        res = client.post("/query", json={"question": "What is the secret override code for the shrimp feeder?"})
        assert res.status_code == 200
        query_result = res.json()
        
        assert query_result["diagnostics"]["abstained"] is True
        assert len(query_result["citations"]) == 0
