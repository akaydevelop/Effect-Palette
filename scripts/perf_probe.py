from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app  # noqa: E402


def measure(callable_obj, iterations: int) -> dict[str, float]:
    samples = []
    for _ in range(iterations):
        started = time.perf_counter()
        callable_obj()
        samples.append((time.perf_counter() - started) * 1000.0)
    samples.sort()
    return {
        "median_ms": round(statistics.median(samples), 3),
        "p95_ms": round(samples[min(len(samples) - 1, int(len(samples) * 0.95))], 3),
        "max_ms": round(max(samples), 3),
    }


def main() -> int:
    loader = app.EffectsLoader()
    report = {
        "items": len(loader.snapshot.indexed_items),
        "search": {},
    }
    for query in ("s", "bl", "blur", "earthquake", "color correction"):
        report["search"][query] = measure(lambda query=query: loader.search(query), 150)

    failures = []
    for query, result in report["search"].items():
        if result["p95_ms"] > 5.0:
            failures.append(f"search {query!r} p95 exceeded 5ms: {result['p95_ms']}ms")

    if app.HAS_QT:
        palette = app.create_palette()
        deadline = time.time() + 10
        while not palette._loader_ready and time.time() < deadline:
            palette.root.update()
            time.sleep(0.005)

        def refresh_first_character():
            palette.entry.setText("")
            palette.entry.setText("s")

        report["qt_refresh"] = measure(refresh_first_character, 50)
        if report["qt_refresh"]["p95_ms"] > 20.0:
            failures.append(f"Qt refresh p95 exceeded 20ms: {report['qt_refresh']['p95_ms']}ms")
        palette.shutdown()
        palette.root.destroy()

    print(json.dumps(report, indent=2))
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
