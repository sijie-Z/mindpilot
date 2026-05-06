"""
Load testing for MindPilot backend.
Uses concurrent requests to test performance under load.

Run with: python -m tests.load_test
Or with locust: locust -f tests/load_test.py --host=http://127.0.0.1:8002
"""
import asyncio
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = "http://127.0.0.1:8002"


def measure_latency(method: str, url: str, **kwargs) -> tuple[float, int]:
    """Measure response time and status code."""
    start = time.time()
    try:
        with httpx.Client(base_url=BASE_URL, timeout=60) as client:
            if method == "GET":
                r = client.get(url, **kwargs)
            else:
                r = client.post(url, **kwargs)
        latency = (time.time() - start) * 1000  # ms
        return latency, r.status_code
    except Exception:
        return -1, 0


async def async_measure(method: str, url: str, **kwargs) -> tuple[float, int]:
    """Async version for higher concurrency."""
    start = time.time()
    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
            if method == "GET":
                r = await client.get(url, **kwargs)
            else:
                r = await client.post(url, **kwargs)
        latency = (time.time() - start) * 1000
        return latency, r.status_code
    except Exception:
        return -1, 0


def test_concurrent_chat(n: int = 20, workers: int = 10) -> dict:
    """
    Run n concurrent chat requests.
    Reports latency percentiles.
    """
    queries = [
        "What is RAG?",
        "How does MindPilot work?",
        "What are the key features?",
        "How to use the API?",
        "What is LangGraph?",
    ]

    results = []

    def worker_batch():
        batch_results = []
        for _ in range(n // workers):
            q = queries[int(time.time()) % len(queries)]
            lat, code = measure_latency("POST", "/api/chat/", json={"query": q})
            batch_results.append((lat, code))
        return batch_results

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker_batch) for _ in range(workers)]
        for future in as_completed(futures):
            results.extend(future.result())

    total_time = time.time() - start_time

    latencies = [r[0] for r in results if r[0] > 0]
    status_codes = [r[1] for r in results]

    if not latencies:
        return {"error": "No successful requests"}

    sorted_lat = sorted(latencies)
    p95_idx = int(len(sorted_lat) * 0.95)
    p99_idx = int(len(sorted_lat) * 0.99)

    return {
        "total_requests": n,
        "successful": len(latencies),
        "failed": n - len(latencies),
        "total_time_ms": total_time * 1000,
        "throughput_rps": n / total_time,
        "latency": {
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "mean_ms": statistics.mean(latencies),
            "median_ms": statistics.median(latencies),
            "p95_ms": sorted_lat[min(p95_idx, len(sorted_lat) - 1)],
            "p99_ms": sorted_lat[min(p99_idx, len(sorted_lat) - 1)],
        },
        "status_codes": dict(statistics.Counter(status_codes)),
    }


async def test_async_chat(n: int = 50) -> dict:
    """Async test for higher concurrency."""
    queries = [f"Test query {i}" for i in range(n)]

    start_time = time.time()

    tasks = [
        async_measure("POST", "/api/chat/", json={"query": q})
        for q in queries
    ]

    results = await asyncio.gather(*tasks)

    total_time = time.time() - start_time
    latencies = [r[0] for r in results if r[0] > 0]
    status_codes = [r[1] for r in results]

    if not latencies:
        return {"error": "No successful requests"}

    return {
        "total_requests": n,
        "successful": len(latencies),
        "failed": n - len(latencies),
        "total_time_ms": total_time * 1000,
        "throughput_rps": n / total_time,
        "latency": {
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "mean_ms": statistics.mean(latencies),
            "median_ms": statistics.median(latencies),
            "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies),
            "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) >= 100 else max(latencies),
        },
        "status_codes": dict(statistics.Counter(status_codes)),
    }


async def test_sse_concurrent(n: int = 10) -> dict:
    """Test concurrent SSE stream connections."""
    queries = [f"SSE test {i}" for i in range(n)]

    async def stream_one(query: str) -> tuple[float, int]:
        start = time.time()
        try:
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
                async with client.stream("POST", "/api/chat/stream", json={"query": query}) as resp:
                    count = 0
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            count += 1
                    latency = (time.time() - start) * 1000
                    return latency, resp.status_code, count
        except Exception:
            return -1, 0, 0

    start_time = time.time()
    results = await asyncio.gather(*[stream_one(q) for q in queries])
    total_time = time.time() - start_time

    latencies = [r[0] for r in results if r[0] > 0]
    event_counts = [r[2] for r in results]

    return {
        "total_connections": n,
        "successful": len(latencies),
        "total_time_ms": total_time * 1000,
        "throughput_conn_per_sec": n / total_time,
        "latency": {
            "min_ms": min(latencies) if latencies else 0,
            "max_ms": max(latencies) if latencies else 0,
            "mean_ms": statistics.mean(latencies) if latencies else 0,
        },
        "events_per_stream": {
            "min": min(event_counts) if event_counts else 0,
            "max": max(event_counts) if event_counts else 0,
            "mean": statistics.mean(event_counts) if event_counts else 0,
        },
    }


async def test_milvus_operations(n: int = 100) -> dict:
    """Test Milvus vector insert/search performance."""
    import numpy as np

    from app.rag.embedder import embedder
    from app.rag.vector_store import vector_store

    # Test embed speed
    queries = [f"test query {i}" for i in range(n)]
    start = time.time()
    embeddings = await embedder.embed_batch(queries)
    embed_time = (time.time() - start) * 1000

    # Test insert
    chunk_ids = [f"load_test_{i}" for i in range(n)]
    vectors = np.array(embeddings, dtype=np.float32)

    start = time.time()
    vector_store.insert_vectors(chunk_ids, vectors, "load_test")
    insert_time = (time.time() - start) * 1000

    # Test search
    query_emb = embeddings[0]
    start = time.time()
    for _ in range(10):
        results = vector_store.search(query_emb, top_k=10)
    search_time = ((time.time() - start) / 10) * 1000

    return {
        "embed_batch_n": n,
        "embed_time_ms": embed_time,
        "embed_per_doc_ms": embed_time / n,
        "insert_vectors_n": n,
        "insert_time_ms": insert_time,
        "insert_per_vector_ms": insert_time / n,
        "search_avg_ms": search_time,
        "search_results": len(results) if results else 0,
    }


async def test_rag_pipeline(n: int = 20) -> dict:
    """Test full RAG pipeline under load."""
    queries = [
        "What is MindPilot?",
        "How does RAG work?",
        "What features does it have?",
        "Explain LangGraph",
        "How to use skills?",
    ]

    results = []
    start_time = time.time()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
        for q in queries * (n // len(queries)):
            req_start = time.time()
            try:
                r = await client.post("/api/chat/", json={
                    "query": q,
                    "knowledge_id": "6facc341-6281-4ecb-8a19-c8e0c9201446",
                })
                elapsed = (time.time() - req_start) * 1000
                results.append({
                    "query": q,
                    "latency_ms": elapsed,
                    "status": r.status_code,
                    "answer_len": len(r.json().get("answer", "")),
                    "sources_count": len(r.json().get("sources", [])),
                })
            except Exception as e:
                results.append({
                    "query": q,
                    "latency_ms": -1,
                    "status": 0,
                    "error": str(e),
                })

    total_time = time.time() - start_time
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]

    return {
        "total_requests": len(results),
        "successful": len(latencies),
        "total_time_ms": total_time * 1000,
        "throughput_rps": len(results) / total_time,
        "latency": {
            "min_ms": min(latencies) if latencies else 0,
            "max_ms": max(latencies) if latencies else 0,
            "mean_ms": statistics.mean(latencies) if latencies else 0,
            "median_ms": statistics.median(latencies) if latencies else 0,
        },
        "sample_results": results[:3],
    }


def _fmt(val, spec=""):
    """Safely format a value, handling N/A and None."""
    if val is None or val == "N/A":
        return "N/A"
    try:
        return f"{val:{spec}}"
    except (ValueError, TypeError):
        return str(val)


def run_all_load_tests():
    """Run all load tests and print report."""
    print("=" * 60)
    print("MindPilot Load Test Report")
    print("=" * 60)
    print()

    # Test 0: Health endpoint (fast, no LLM)
    print("0. Health Endpoint (50 concurrent)...")
    async def health_test():
        start = time.time()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as c:
            tasks = []
            for _ in range(50):
                async def h():
                    s = time.time()
                    r = await c.get("/health")
                    return (time.time() - s) * 1000, r.status_code
                tasks.append(h())
            results = await asyncio.gather(*tasks)
        total = (time.time() - start) * 1000
        ok = [r for r in results if r[0] > 0]
        lats = sorted([r[0] for r in ok]) if ok else []
        return {
            "total_requests": 50,
            "successful": len(ok),
            "total_time_ms": total,
            "throughput_rps": 50 / (total / 1000),
            "latency": {
                "min_ms": lats[0] if lats else 0,
                "max_ms": lats[-1] if lats else 0,
                "mean_ms": statistics.mean(lats) if lats else 0,
                "p50_ms": lats[len(lats)//2] if lats else 0,
                "p95_ms": lats[int(len(lats)*0.95)] if len(lats) >= 20 else (lats[-1] if lats else 0),
            }
        }
    result0 = asyncio.run(health_test())
    print(f"   Throughput: {_fmt(result0.get('throughput_rps'), '.1f')} req/s")
    print(f"   Latency (p50): {_fmt(result0.get('latency', {}).get('p50_ms'), '.1f')} ms")
    print(f"   Latency (p95): {_fmt(result0.get('latency', {}).get('p95_ms'), '.1f')} ms")
    print(f"   Success: {result0.get('successful', 0)}/{result0.get('total_requests', 0)}")
    print()

    print("1. Concurrent Chat (5 requests, 5 workers)...")
    result = test_concurrent_chat(n=5, workers=5)
    print(f"   Throughput: {_fmt(result.get('throughput_rps'), '.2f')} req/s")
    lat = result.get('latency', {})
    print(f"   Latency (p95): {_fmt(lat.get('p95_ms'), '.0f')} ms")
    print(f"   Success: {result.get('successful', 0)}/{result.get('total_requests', 0)}")
    if 'error' in result:
        print(f"   Error: {result['error']}")
    print()

    print("2. Async Chat (10 concurrent)...")
    result2 = asyncio.run(test_async_chat(10))
    print(f"   Throughput: {_fmt(result2.get('throughput_rps'), '.2f')} req/s")
    lat2 = result2.get('latency', {})
    print(f"   Latency (p95): {_fmt(lat2.get('p95_ms'), '.0f')} ms")
    if 'error' in result2:
        print(f"   Error: {result2['error']}")
    print()

    print("3. SSE Concurrent (3 streams)...")
    result3 = asyncio.run(test_sse_concurrent(3))
    print(f"   Throughput: {_fmt(result3.get('throughput_conn_per_sec'), '.2f')} conn/s")
    lat3 = result3.get('latency', {})
    print(f"   Mean latency: {_fmt(lat3.get('mean_ms'), '.0f')} ms")
    print()

    print("4. RAG Pipeline (5 requests)...")
    result4 = asyncio.run(test_rag_pipeline(5))
    print(f"   Throughput: {_fmt(result4.get('throughput_rps'), '.2f')} req/s")
    lat4 = result4.get('latency', {})
    print(f"   Latency (mean): {_fmt(lat4.get('mean_ms'), '.0f')} ms")
    if result4.get('sample_results'):
        print(f"   Sample: {result4['sample_results'][0].get('latency_ms', 'N/A')} ms")
    print()

    print("5. Vector Operations (Milvus)...")
    try:
        result5 = asyncio.run(test_milvus_operations(5))
        print(f"   Embed (5 docs): {_fmt(result5.get('embed_time_ms'), '.0f')} ms")
        print(f"   Insert (5 vectors): {_fmt(result5.get('insert_time_ms'), '.0f')} ms")
        print(f"   Search (avg): {_fmt(result5.get('search_avg_ms'), '.2f')} ms")
    except Exception as e:
        print(f"   Milvus not connected: {e}")
    print()

    print("=" * 60)
    print("Load test complete")


if __name__ == "__main__":
    run_all_load_tests()
