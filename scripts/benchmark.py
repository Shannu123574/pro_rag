import requests
import time
import statistics
import os
import tempfile

API_URL = "http://localhost:8000"

def wait_for_ready():
    print("Waiting for API to be ready...")
    for _ in range(60):
        try:
            r = requests.get(f"{API_URL}/ready")
            if r.status_code == 200:
                print("API is ready.")
                return
        except requests.ConnectionError:
            pass
        time.sleep(1)
    raise RuntimeError("API not ready")

def benchmark_query(name, question, iterations=10):
    latencies = []
    # Warmup
    requests.post(f"{API_URL}/query", json={"question": question})
    
    for _ in range(iterations):
        start = time.perf_counter()
        r = requests.post(f"{API_URL}/query", json={"question": question})
        latencies.append(time.perf_counter() - start)
        r.raise_for_status()
        
    print(f"--- Benchmark: {name} ---")
    print(f"Iterations: {iterations}")
    print(f"Average: {statistics.mean(latencies):.4f}s")
    print(f"Median: {statistics.median(latencies):.4f}s")
    latencies.sort()
    print(f"P90: {latencies[int(len(latencies)*0.9)]:.4f}s")
    print(f"P95: {latencies[int(len(latencies)*0.95)]:.4f}s")
    print(f"Max: {max(latencies):.4f}s\n")

def benchmark_ingestion(name, content):
    latencies = []
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(content.encode('utf-8'))
        temp_path = f.name
        
    for i in range(5):
        # We need a unique name to bypass duplicate checking
        unique_content = content + f" Iteration {i}"
        with open(temp_path, "w") as f:
            f.write(unique_content)
            
        start = time.perf_counter()
        with open(temp_path, "rb") as f:
            r = requests.post(f"{API_URL}/ingest", files={"file": (f"{name}_{i}.txt", f, "text/plain")})
        latencies.append(time.perf_counter() - start)
        r.raise_for_status()
        
    os.remove(temp_path)
    print(f"--- Benchmark: Ingestion {name} ---")
    print(f"Average: {statistics.mean(latencies):.4f}s")
    print(f"Median: {statistics.median(latencies):.4f}s")
    latencies.sort()
    print(f"P90: {latencies[int(len(latencies)*0.9)]:.4f}s")
    print(f"Max: {max(latencies):.4f}s\n")


if __name__ == "__main__":
    wait_for_ready()
    
    benchmark_query("Single warm query", "What is Pond 7?", iterations=1)
    benchmark_query("Repeated warm queries", "How often is Pond 7 checked?", iterations=10)
    benchmark_query("Diverse query", "Tell me about the emergency protocols for the facility.", iterations=10)
    benchmark_query("Long query", "Can you explain in detail how often Pond 7 is checked according to the latest operational guidelines and if there are any exceptions to this rule?", iterations=10)
    benchmark_query("Unsupported query", "What is the capital of France?", iterations=10)
    
    benchmark_ingestion("Small Document", "This is a small test document.")
    benchmark_ingestion("Medium Document", "This is a medium document. " * 100)
    benchmark_ingestion("Large Document", "This is a large document. " * 1000)
