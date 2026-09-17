import time
from tests.dataset import EVAL_DATASET
from app.retrieval import retrieve
from app.generation import get_generator, build_evidence

def evidence_count_experiment():
    counts = [1, 2, 4, 6]
    generator = get_generator()

    results = {c: [] for c in counts}

    for case in EVAL_DATASET:
        q = case["question"]
        try:
            ev_tuples = retrieve(q)
        except Exception:
            continue

        for c in counts:
            limited_ev = ev_tuples[:c]
            context = build_evidence(limited_ev)
            prompt = f"Use evidence... {context} \nQuestion: {q}\nAnswer:"
            
            t0 = time.perf_counter()
            generator(prompt, max_new_tokens=96, do_sample=False)
            t1 = time.perf_counter()
            results[c].append(t1 - t0)

    print("\nEvidence Count Latency (with 96 tokens):")
    for c in counts:
        times = sorted(results[c])
        if not times: continue
        p50 = times[len(times)//2]
        p90 = times[int(len(times)*0.9)]
        mx = times[-1]
        print(f"Chunks: {c} | P50: {p50*1000:7.2f}ms | P90: {p90*1000:7.2f}ms | Max: {mx*1000:7.2f}ms")

if __name__ == "__main__":
    evidence_count_experiment()
