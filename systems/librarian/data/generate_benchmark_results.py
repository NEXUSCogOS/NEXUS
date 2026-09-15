#!/usr/bin/env python3
"""Generate retrieval benchmark results as mission deliverable.

Mission section 15 & 32: Produces RETRIEVAL_BENCHMARK.json with measured
recall@k, precision@k, MRR, source-quality-weighted retrieval scores.
"""

import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from academic.benchmark import run_benchmark
from academic.ingest_real_sources import ingest_all
from academic.store import AcademicStore


def main():
    data_dir = Path(__file__).parent
    db_path = data_dir / "academic_corpus.db"
    store = AcademicStore(db_path)

    # Ensure real manifest is ingested
    ingest_all(store)

    # Run benchmark
    results = run_benchmark(store, k=5)

    # Write results
    output_path = data_dir / "RETRIEVAL_BENCHMARK.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Benchmark results written to {output_path}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
