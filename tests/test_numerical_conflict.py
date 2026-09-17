import pytest
from fastapi.testclient import TestClient
from app.main import app
import time

client = TestClient(app)

with client:
    for _ in range(60):
        if client.get("/health").json()["status"] == "ok":
            break
        time.sleep(1)

CONFLICT_DOCS = [
    # 1. Genuinely contradictory facts
    {
        "docs": [
            ("doc1.txt", b"The optimal temperature for Pond 1 is 25C."),
            ("doc2.txt", b"The optimal temperature for Pond 1 is 30C.")
        ],
        "question": "What is the optimal temperature for Pond 1?",
        "expect_conflict": True
    },
    # 2. Same value, different units (Not a conflict)
    {
        "docs": [
            ("doc3.txt", b"The pipe length is 100 cm."),
            ("doc4.txt", b"The pipe length is 1 meter.")
        ],
        "question": "What is the pipe length?",
        "expect_conflict": False
    },
    # 3. Different attributes (Not a conflict)
    {
        "docs": [
            ("doc5.txt", b"The salinity is 15 ppt."),
            ("doc6.txt", b"The pH is 7.5.")
        ],
        "question": "What are the water quality parameters?",
        "expect_conflict": False
    },
    # 4. Different entities (Not a conflict)
    {
        "docs": [
            ("doc7.txt", b"Pond 1 requires 100 kg of feed."),
            ("doc8.txt", b"Pond 2 requires 150 kg of feed.")
        ],
        "question": "How much feed is required?",
        "expect_conflict": False
    },
    # 5. Different conditions (Not a conflict)
    {
        "docs": [
            ("doc9.txt", b"During summer, oxygen should be 5 mg/L."),
            ("doc10.txt", b"During winter, oxygen should be 7 mg/L.")
        ],
        "question": "What should the oxygen levels be?",
        "expect_conflict": False
    }
]

@pytest.mark.parametrize("case", CONFLICT_DOCS)
def test_numerical_conflict(case):
    doc_ids = []
    for filename, content in case["docs"]:
        res = client.post("/ingest", files={"file": (filename, content, "text/plain")})
        assert res.status_code == 200
        doc_ids.append(res.json()["document_id"])
    
    try:
        q_res = client.post("/query", json={"question": case["question"]})
        assert q_res.status_code == 200
        answer = q_res.json()["answer"].lower()
        
        has_conflict = "conflict" in answer or "contradictory" in answer or "vs" in answer
        
        if case["expect_conflict"]:
            assert has_conflict, f"Expected conflict detection, but got: {answer}"
        else:
            assert not has_conflict, f"False positive conflict detected: {answer}"
            
    finally:
        for doc_id in doc_ids:
            client.delete(f"/documents/{doc_id}")
