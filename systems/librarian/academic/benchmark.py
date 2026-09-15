"""Hand-verifiable retrieval benchmark and evaluator.

NEW module, NEXUS Librarian F4. `BENCHMARK_QUESTIONS` below is
hand-authored against the REAL, known contents of the 22-source academic
corpus ingested this mission (`real_source_manifest.json`) — every
`expected_relevant` id was chosen by a human/audit read of that paper's
real abstract, not generated or guessed. This is what "hand-verifiable"
means here: the ground truth is checkable by anyone reading
`real_source_manifest.json` directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from academic.retrieval import search
from academic.store import AcademicStore
from academic.taxonomy import SourceType, evidence_weight


@dataclass(frozen=True)
class BenchmarkQuestion:
    question_id: str
    domain: str
    query: str
    key_concepts: list[str]
    expected_relevant: list[str]  # arxiv ids, hand-verified against real_source_manifest.json
    known_distractors: list[str]  # arxiv ids present in the corpus but NOT relevant to this query
    acceptable_evidence_note: str


BENCHMARK_QUESTIONS: list[BenchmarkQuestion] = [
    BenchmarkQuestion(
        question_id="Q1_cognitive_architecture",
        domain="cognitive_architecture",
        query="working memory cognitive architecture",
        key_concepts=["working memory", "cognitive architecture", "iterative updating"],
        expected_relevant=["2103.09072", "2203.17255", "2606.28045", "2406.09823"],
        known_distractors=["2012.10390"],  # global workspace theory -- related concept, different specific claim (working memory vs. workspace integration)
        acceptable_evidence_note="Any of the 4 expected papers explicitly discusses working memory as a structural element of a cognitive architecture.",
    ),
    BenchmarkQuestion(
        question_id="Q2_autonomous_engineering",
        domain="autonomous_engineering",
        query="large language model agent tool use failure",
        key_concepts=["LLM agent", "tool use", "failure modes"],
        expected_relevant=["2604.00835", "2607.05775", "2602.12430"],
        known_distractors=["2201.12885", "cs/9905014"],  # metacognition and classical hierarchical RL -- related field, not about LLM agent tool-use failure specifically
        acceptable_evidence_note="Any of the 3 expected papers explicitly surveys or synthesizes LLM agent tool-use/failure literature.",
    ),
    BenchmarkQuestion(
        question_id="Q3_evidence_provenance",
        domain="evidence_provenance",
        query="reproducibility meta-analysis evidence synthesis",
        key_concepts=["reproducibility", "meta-analysis", "evidence synthesis"],
        expected_relevant=["1907.01463", "2504.20113", "2412.12945"],
        known_distractors=["2403.06779"],  # ML survey in asset pricing -- unrelated to methodology/reproducibility
        acceptable_evidence_note="Any of the 3 expected papers is directly about reproducibility standards or meta-analysis methodology.",
    ),
    BenchmarkQuestion(
        question_id="Q4_distributed_systems",
        domain="distributed_systems",
        query="self-healing fault tolerance distributed systems",
        key_concepts=["self-healing", "fault tolerance", "distributed systems"],
        expected_relevant=["2010.11146", "2007.05261", "1805.03549", "2407.06738"],
        known_distractors=["2104.08663"],  # BEIR IR benchmark -- unrelated to fault tolerance
        acceptable_evidence_note="Any of the 4 expected papers is directly about self-healing/fault-tolerance mechanisms in distributed systems.",
    ),
    BenchmarkQuestion(
        question_id="Q5_geospatial_science",
        domain="dat_ai_geospatial",
        query="land use classification remote sensing deep learning",
        key_concepts=["land use classification", "remote sensing", "deep learning"],
        expected_relevant=["1908.03438", "2107.10894"],
        known_distractors=["2004.01504"],  # financial ML -- unrelated domain despite sharing "deep learning"/"ML" vocabulary
        acceptable_evidence_note="Both expected papers directly perform land-use/industrial-site classification from satellite imagery using deep learning.",
    ),
]


@dataclass
class QuestionResult:
    question_id: str
    retrieved_ids: list[str]
    expected_relevant: list[str]
    recall_at_k: float
    precision_at_k: float
    reciprocal_rank: float
    distractors_incorrectly_retrieved: list[str]
    source_quality_weighted_score: float


def _arxiv_id_of(source_id: str) -> str:
    # academic source_id is "arxiv:<id>" per academic/identity.py's preferred-order scheme
    return source_id.split(":", 1)[1] if ":" in source_id else source_id


def evaluate_question(store: AcademicStore, q: BenchmarkQuestion, *, k: int = 5) -> QuestionResult:
    hits = search(store, q.query, max_results=k, min_matched_terms=1)
    retrieved_ids = [_arxiv_id_of(h.source_id) for h in hits]

    relevant_set = set(q.expected_relevant)
    retrieved_set = set(retrieved_ids)
    true_positives = retrieved_set & relevant_set

    recall = len(true_positives) / len(relevant_set) if relevant_set else 0.0
    precision = len(true_positives) / len(retrieved_ids) if retrieved_ids else 0.0

    reciprocal_rank = 0.0
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_set:
            reciprocal_rank = 1.0 / rank
            break

    distractors_hit = [rid for rid in retrieved_ids if rid in set(q.known_distractors)]

    quality_scores = []
    for h in hits:
        rank_value = evidence_weight(SourceType(h.source_type))
        quality_scores.append(1.0 / (1 + rank_value))
    quality_weighted = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    return QuestionResult(
        question_id=q.question_id,
        retrieved_ids=retrieved_ids,
        expected_relevant=q.expected_relevant,
        recall_at_k=recall,
        precision_at_k=precision,
        reciprocal_rank=reciprocal_rank,
        distractors_incorrectly_retrieved=distractors_hit,
        source_quality_weighted_score=quality_weighted,
    )


def run_benchmark(store: AcademicStore, *, k: int = 5) -> dict:
    results = [evaluate_question(store, q, k=k) for q in BENCHMARK_QUESTIONS]
    mean_recall = sum(r.recall_at_k for r in results) / len(results)
    mean_precision = sum(r.precision_at_k for r in results) / len(results)
    mrr = sum(r.reciprocal_rank for r in results) / len(results)
    return {
        "k": k,
        "questions": [
            {
                "question_id": r.question_id,
                "retrieved_ids": r.retrieved_ids,
                "expected_relevant": r.expected_relevant,
                f"recall_at_{k}": round(r.recall_at_k, 3),
                f"precision_at_{k}": round(r.precision_at_k, 3),
                "reciprocal_rank": round(r.reciprocal_rank, 3),
                "distractors_incorrectly_retrieved": r.distractors_incorrectly_retrieved,
                "source_quality_weighted_score": round(r.source_quality_weighted_score, 3),
            }
            for r in results
        ],
        f"mean_recall_at_{k}": round(mean_recall, 3),
        f"mean_precision_at_{k}": round(mean_precision, 3),
        "mrr": round(mrr, 3),
    }
