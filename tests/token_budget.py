import time
from tests.dataset import EVAL_DATASET
from app.retrieval import retrieve
from app.generation import get_generator, build_evidence, extract_citations

def token_budget_experiment():
    budgets = [32, 64, 96, 128, 180]
    generator = get_generator()

    results = {b: [] for b in budgets}

    for case in EVAL_DATASET:
        q = case["question"]
        try:
            ev_tuples = retrieve(q)
        except Exception:
            continue

        context = build_evidence(ev_tuples)
        prompt = f"Use evidence... {context} \nQuestion: {q}\nAnswer:"
        
        for b in budgets:
            t0 = time.perf_counter()
            generator(prompt, max_new_tokens=b, do_sample=False)
            t1 = time.perf_counter()
            results[b].append(t1 - t0)

    print("\nToken Budget Latency:")
    for b in budgets:
        times = sorted(results[b])
        if not times: continue
        p50 = times[len(times)//2]
        p90 = times[int(len(times)*0.9)]
        mx = times[-1]
        print(f"Tokens: {b:3d} | P50: {p50*1000:7.2f}ms | P90: {p90*1000:7.2f}ms | Max: {mx*1000:7.2f}ms")

if __name__ == "__main__":
    token_budget_experiment()
