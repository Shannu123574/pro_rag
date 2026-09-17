import pytest
from fastapi.testclient import TestClient
from app.main import app, ingest_limiter
from app.db import SessionLocal, Chunk

client = TestClient(app)

def setup_function():
    ingest_limiter.requests.clear()

def test_ingestion_duplicate():
    content = b"This is a test document."
    files1 = {"file": ("doc1.txt", content, "text/plain")}
    res1 = client.post("/ingest", files=files1)
    assert res1.status_code == 200
    doc_id1 = res1.json()["document_id"]

    # exact same
    files2 = {"file": ("doc1.txt", content, "text/plain")}
    res2 = client.post("/ingest", files=files2)
    assert res2.status_code == 200
    assert res2.json()["document_id"] == doc_id1

    # Same content, different name
    files3 = {"file": ("doc2.txt", content, "text/plain")}
    res3 = client.post("/ingest", files=files3)
    assert res3.status_code == 200
    assert res3.json()["document_id"] == doc_id1
    
def test_empty_document():
    files = {"file": ("empty.txt", b"", "text/plain")}
    res = client.post("/ingest", files=files)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()

def test_malformed_document():
    # some garbage bytes as pdf
    files = {"file": ("bad.pdf", b"garbage123", "application/pdf")}
    res = client.post("/ingest", files=files)
    assert res.status_code == 400
