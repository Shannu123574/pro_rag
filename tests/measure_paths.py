import time
from tests.dataset import EVAL_DATASET
from app.retrieval import retrieve
from app.generation import answer, deterministic_answer, evidence_is_sufficient

def measure_paths():
    total_det_time = 0
    total_det_hits = 0

    total_fallback_time = 0
    total_fallback_hits = 0

    total_abstain_hits = 0

    print("Generation Path Breakdown:")
    for case in EVAL_DATASET:
        q = case["question"]
        try:
            ev_tuples = retrieve(q)
        except Exception as e:
            print(f"Error retrieving for {q}: {e}")
            continue

        start = time.perf_counter()
        
        # Determine path
        det_result = deterministic_answer(q, ev_tuples)
        if det_result:
            duration = time.perf_counter() - start
            total_det_time += duration
            total_det_hits += 1
            continue
            
        if not evidence_is_sufficient(q, ev_tuples):
            total_abstain_hits += 1
            continue

        # We need to measure actual fallback time
        from app.generation import get_generator, build_evidence, extract_citations
        generator = get_generator()
        context = build_evidence(ev_tuples)
        prompt = f"Use evidence... {context} \nQuestion: {q}\nAnswer:"
        
        t0 = time.perf_counter()
        generator(prompt, max_new_tokens=180, do_sample=False)
        t1 = time.perf_counter()
        
        total_fallback_time += (t1 - t0)
        total_fallback_hits += 1

    print(f"\nDeterministic Fast Path:")
    print(f"Hits: {total_det_hits} / {len(EVAL_DATASET)}")
    print(f"Avg Latency: {(total_det_time/total_det_hits*1000):.2f} ms" if total_det_hits else "N/A")

    print(f"\nFLAN-T5 Fallback:")
    print(f"Hits: {total_fallback_hits} / {len(EVAL_DATASET)}")
    print(f"Avg Latency: {(total_fallback_time/total_fallback_hits*1000):.2f} ms" if total_fallback_hits else "N/A")

    print(f"\nAbstention:")
    print(f"Hits: {total_abstain_hits} / {len(EVAL_DATASET)}")

if __name__ == "__main__":
    measure_paths()
