import time
import torch
from tests.dataset import EVAL_DATASET
from app.retrieval import retrieve
from app.generation import get_generator, build_evidence

def threading_benchmark():
    thread_counts = [1, 2, 4, 8]
    generator = get_generator()

    results = {tc: [] for tc in thread_counts}

    for tc in thread_counts:
        torch.set_num_threads(tc)
        print(f"\nEvaluating with {tc} threads...")
        for case in EVAL_DATASET[:5]:  # Just first 5 cases to save time
            q = case["question"]
            try:
                ev_tuples = retrieve(q)
            except Exception:
                continue

            context = build_evidence(ev_tuples)
            prompt = f"Use evidence... {context} \nQuestion: {q}\nAnswer:"
            
            t0 = time.perf_counter()
            generator(prompt, max_new_tokens=96, do_sample=False)
            t1 = time.perf_counter()
            results[tc].append(t1 - t0)

    print("\nCPU Threading Latency (with 96 tokens, 5 queries):")
    for tc in thread_counts:
        times = sorted(results[tc])
        if not times: continue
        p50 = times[len(times)//2]
        p90 = times[int(len(times)*0.9)]
        mx = times[-1]
        print(f"Threads: {tc} | P50: {p50*1000:7.2f}ms | P90: {p90*1000:7.2f}ms | Max: {mx*1000:7.2f}ms")

if __name__ == "__main__":
    threading_benchmark()
