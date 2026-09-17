import json
from tests.dataset import EVAL_DATASET
from app.retrieval import retrieve_with_diagnostics
from app.generation import answer, build_evidence

def diagnose():
    for case in EVAL_DATASET:
        q = case["question"]
        try:
            chunks, diagnostics = retrieve_with_diagnostics(q)
        except Exception:
            continue
            
        result = answer(q, chunks)
        ans_lower = result["answer"].lower()
        failures = []
        for concept in case["required_concepts"]:
            if concept.lower() not in ans_lower:
                failures.append(f"Missing concept: {concept}")
                
        for concept in case["forbidden_concepts"]:
            if concept.lower() in ans_lower:
                failures.append(f"Forbidden concept included: {concept}")
                
        is_abstained = result["answer"] == "I don't have sufficient evidence in the knowledge base to answer that."
        if case["should_abstain"] and not is_abstained:
            failures.append("Failed to abstain")
        if not case["should_abstain"] and is_abstained:
            failures.append("Erroneously abstained")
        
        if not failures:
            continue
            
        print(f"============================================================")
        print(f"FAILING QUESTION: {q}")
        print(f"Expected concept missing: {failures}")
        print(f"Generated Answer: {result['answer']}")
        print(f"Retrieved Chunks:")
        for i, (c, score) in enumerate(chunks):
            print(f"  [{i+1}] Source: {c.source}")
            print(f"      Content: {c.content}")
        print(f"============================================================\n")

if __name__ == "__main__":
    diagnose()
