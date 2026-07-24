import resource
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

from .retrieval import RETRIEVAL_PROFILES, RetrievalService
from .vector_store import VectorStore


def benchmark_synthetic_corpus(
    *,
    document_count: int = 300,
    query_count: int = 24,
) -> dict[str, Any]:
    if document_count < 100:
        raise ValueError("Use at least 100 documents for a release benchmark.")
    if query_count < 3:
        raise ValueError("Use at least three benchmark queries.")

    with tempfile.TemporaryDirectory(prefix="heritage-benchmark-") as directory:
        store = VectorStore(Path(directory), "heritage_release_benchmark")
        chunks = [_benchmark_chunk(index) for index in range(document_count)]
        indexing_started = perf_counter()
        store.upsert(chunks)
        indexing_seconds = perf_counter() - indexing_started
        retrieval = RetrievalService(
            vector_store=store,
            candidate_k=14,
            top_k=7,
            minimum_relevance=0.28,
        )
        mode_reports: dict[str, dict[str, Any]] = {}
        for mode in ("quick", "medium", "deep"):
            latencies: list[float] = []
            hits = 0
            for offset in range(query_count):
                document_index = (offset * 11) % document_count
                query = (
                    f"What is the benchmark reference code heritage{document_index:04d}?"
                )
                started = perf_counter()
                result = retrieval.retrieve_with_mode(query, mode)  # type: ignore[arg-type]
                latencies.append((perf_counter() - started) * 1000)
                expected_id = f"benchmark-doc-{document_index:04d}"
                hits += int(any(source.document_id == expected_id for source in result.sources))
            mode_reports[mode] = {
                "profile": RETRIEVAL_PROFILES[mode],
                "queries": query_count,
                "hit_rate": round(hits / query_count, 3),
                "latency_ms": {
                    "p50": round(_percentile(latencies, 50), 2),
                    "p95": round(_percentile(latencies, 95), 2),
                    "max": round(max(latencies), 2),
                },
            }
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_rss_mib = (
            peak_rss / (1024 * 1024)
            if sys.platform == "darwin"
            else peak_rss / 1024
        )
        return {
            "kind": "synthetic-local-retrieval",
            "documents": document_count,
            "chunks": store.count,
            "queries_per_mode": query_count,
            "indexing_seconds": round(indexing_seconds, 3),
            "peak_rss_mib": round(peak_rss_mib, 1),
            "modes": mode_reports,
            "targets": {
                "retrieval_p95_ms": 2000,
                "indexing_seconds": 120,
            },
            "passed": (
                indexing_seconds <= 120
                and all(
                    report["latency_ms"]["p95"] <= 2000
                    for report in mode_reports.values()
                )
            ),
            "notes": [
                "Measures local embedding, Chroma indexing, and retrieval only.",
                (
                    "Synthetic hit rate is informational; corpus retrieval quality "
                    "is scored by the labeled evaluation set."
                ),
                "Cloud-provider generation latency and real-document parsing are excluded.",
            ],
        }


def _benchmark_chunk(index: int) -> dict[str, Any]:
    reference = f"heritage{index:04d}"
    return {
        "chunk_id": f"benchmark-chunk-{index:04d}",
        "document_id": f"benchmark-doc-{index:04d}",
        "file_name": f"benchmark-{index:04d}.txt",
        "title": f"Benchmark Document {index:04d}",
        "relative_path": f"benchmark/benchmark-{index:04d}.txt",
        "page_start": 1,
        "page_end": 1,
        "section": "Synthetic release benchmark",
        "text": (
            f"Heritage synthetic release benchmark record {index:04d}. "
            f"The unique benchmark reference code is {reference}. "
            "This record discusses experiential learning, reflection, inquiry, "
            "project work, calendars, and school information."
        ),
        "content_hash": f"benchmark-{index:064d}"[-64:],
    }


def _percentile(values: list[float], percentile: int) -> float:
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[percentile - 1]
