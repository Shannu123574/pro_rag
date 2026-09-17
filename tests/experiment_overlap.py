import os
import time
import copy
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 1. Create a test database
init_engine = create_engine("postgresql+psycopg://rag:rag@db:5432/postgres", isolation_level="AUTOCOMMIT")
with init_engine.connect() as conn:
    try:
        conn.execute(text("DROP DATABASE IF EXISTS rag_exp"))
        conn.execute(text("CREATE DATABASE rag_exp"))
    except Exception as e:
        pass

# 2. Patch database URL and Engine
os.environ["DATABASE_URL"] = "postgresql+psycopg://rag:rag@db:5432/rag_exp"
import app.config
app.config.settings.database_url = os.environ["DATABASE_URL"]

import app.db
app.db.engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
app.db.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=app.db.engine)

with app.db.engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

app.db.Base.metadata.create_all(bind=app.db.engine)

import app.ingest
import app.retrieval
import app.generation
from tests.dataset import EVAL_DATASET
from tests.create_fixtures import load_corpus

def run_experiment(chunk_size, overlap):
    print(f"\n===========================================")
    print(f"EXPERIMENT: chunk_size={chunk_size}, overlap={overlap}")
    print(f"===========================================")
    
    # Apply settings
    app.config.settings.chunk_size = chunk_size
    app.config.settings.chunk_overlap = overlap
    
    # Clean DB
    with app.db.SessionLocal() as db:
        db.query(app.db.Chunk).delete()
        db.query(app.db.Document).delete()
        db.commit()
        
    # Ingest corpus
    corpus = load_corpus()
    for source, content in corpus.items():
        app.ingest.process_file(content.encode("utf-8"), source)
        
    with app.db.SessionLocal() as db:
        chunk_count = db.query(app.db.Chunk).count()
        doc_count = db.query(app.db.Document).count()
        print(f"Ingested {doc_count} docs into {chunk_count} chunks.")
        
    # Evaluate
    evaluate_metrics()

def evaluate_metrics():
    latencies = []
    faithfulness_failures = 0
    citation_failures = 0
    abstention_failures = 0
    mrr_sum = 0
    recall_sum = 0
    
    for case in EVAL_DATASET:
        q = case["question"]
        t0 = time.perf_counter()
        
        # 1. Retrieval
        try:
            chunks, _ = app.retrieval.retrieve_with_diagnostics(q)
            # 2. Generation
            result = app.generation.answer(q, chunks)
        except Exception as e:
            print(f"Error on {q}: {e}")
            continue
            
        t1 = time.perf_counter()
        latencies.append(t1 - t0)
        
        # Check source recall
        retrieved_sources = [c.source for c, _ in chunks]
        if case["expected_source"] in retrieved_sources:
            recall_sum += 1
            idx = retrieved_sources.index(case["expected_source"])
            mrr_sum += 1.0 / (idx + 1)
            
        # Check faithfulness
        ans_lower = result["answer"].lower()
        failed_faith = False
        for concept in case["required_concepts"]:
            if concept.lower() not in ans_lower:
                failed_faith = True
        for concept in case["forbidden_concepts"]:
            if concept.lower() in ans_lower:
                failed_faith = True
        if failed_faith:
            faithfulness_failures += 1
            
        # Check abstention
        is_abstained = result["answer"] == app.generation.ABSTENTION_MESSAGE
        if case["should_abstain"] != is_abstained:
            abstention_failures += 1
            
        # Citation correctness (if not abstained and required concepts exist)
        if not is_abstained and case["required_concepts"]:
            citations = result.get("citations", [])
            valid_citations = 0
            for cit in citations:
                for c, _ in chunks:
                    if cit["source"] == c.source and any(req.lower() in c.content.lower() for req in case["required_concepts"]):
                        valid_citations += 1
                        break
            if len(citations) > 0 and valid_citations != len(citations):
                citation_failures += 1
            if len(citations) == 0:
                citation_failures += 1
                
    latencies.sort()
    p50 = latencies[len(latencies)//2] if latencies else 0
    p90 = latencies[int(len(latencies)*0.9)] if latencies else 0
    p95 = latencies[int(len(latencies)*0.95)] if latencies else 0
    maximum = latencies[-1] if latencies else 0
    
    n = len(EVAL_DATASET)
    print(f"Source Recall@6: {recall_sum/n*100:.1f}%")
    print(f"MRR: {mrr_sum/n:.3f}")
    print(f"Faithfulness Pass Rate: {(n - faithfulness_failures)/n*100:.1f}%")
    print(f"Abstention Accuracy: {(n - abstention_failures)/n*100:.1f}%")
    print(f"Citation Correctness: {100 - citation_failures/n*100:.1f}% (Failures: {citation_failures})")
    print(f"Latencies - P50: {p50*1000:.1f}ms | P90: {p90*1000:.1f}ms | P95: {p95*1000:.1f}ms | Max: {maximum*1000:.1f}ms")

if __name__ == "__main__":
    for overlap in [20, 40, 60, 80, 100]:
        run_experiment(180, overlap)
