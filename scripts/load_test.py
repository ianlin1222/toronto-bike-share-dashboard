from __future__ import annotations

import argparse
import json
import random
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

SEED = 20_260_907


@dataclass(frozen=True)
class RequestResult:
    elapsed_ms: float
    status: int


def one_request(base_url: str, payload: bytes) -> RequestResult:
    request = urllib.request.Request(
        f"{base_url}/v1/recommendations",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    return RequestResult((time.perf_counter() - started) * 1000, status)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=25)
    arguments = parser.parse_args()
    rng = random.Random(SEED)
    payloads = [
        json.dumps(
            {
                "destination": {
                    "lat": 43.6532 + rng.uniform(-0.004, 0.004),
                    "lon": -79.3832 + rng.uniform(-0.004, 0.004),
                },
                "horizon_minutes": rng.choice([5, 10, 15, 30]),
                "radius_m": rng.choice([500, 750, 1000]),
            }
        ).encode()
        for _ in range(arguments.requests)
    ]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=arguments.concurrency) as executor:
        results = list(executor.map(lambda payload: one_request(arguments.base_url, payload), payloads))
    elapsed = time.perf_counter() - started
    timings = sorted(item.elapsed_ms for item in results)
    p95_index = min(round(0.95 * (len(timings) - 1)), len(timings) - 1)
    result = {
        "seed": SEED,
        "requests": len(results),
        "concurrency": arguments.concurrency,
        "p50_ms": statistics.median(timings),
        "p95_ms": timings[p95_index],
        "max_ms": max(timings),
        "error_count": sum(item.status != 200 for item in results),
        "elapsed_seconds": elapsed,
        "requests_per_second": len(results) / elapsed,
        "target": {"contract_errors": 0, "p95_ms_lte": 500},
    }
    print(json.dumps(result, indent=2))
    if result["error_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
