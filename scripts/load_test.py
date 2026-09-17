import requests
import time
import statistics
from concurrent.futures import ThreadPoolExecutor

API_URL = "http://localhost:8000"
QUERY = {"question": "How often is Pond 7 checked?"}

def make_request():
    start = time.perf_counter()
    r = requests.post(f"{API_URL}/query", json=QUERY)
    latency = time.perf_counter() - start
    return r.status_code, latency

def run_concurrency(concurrency, total_requests=20):
    print(f"--- Concurrency: {concurrency} ---")
    start_time = time.perf_counter()
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(lambda _: make_request(), range(total_requests)))
        
    total_time = time.perf_counter() - start_time
    
    latencies = [l for status, l in results if status == 200]
    errors = len([status for status, l in results if status != 200])
    
    print(f"Total time: {total_time:.4f}s")
    print(f"Throughput: {total_requests/total_time:.2f} req/s")
    print(f"Errors: {errors}")
    
    if latencies:
        print(f"Avg Latency: {statistics.mean(latencies):.4f}s")
        latencies.sort()
        print(f"P90 Latency: {latencies[int(len(latencies)*0.9)]:.4f}s\n")

if __name__ == "__main__":
    # Warmup
    requests.post(f"{API_URL}/query", json=QUERY)
    
    for c in [1, 2, 4, 8]:
        run_concurrency(c, total_requests=20)
