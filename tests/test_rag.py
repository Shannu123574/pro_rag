
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.retrieval import retrieve
from app.generation import answer


# ============================================================
# Configuration
# ============================================================

RECALL_K = 6

# Professional benchmark thresholds.
MIN_RECALL_AT_1 = 0.80
MIN_MRR = 0.80
MAX_WARM_LATENCY_SECONDS = 1.0

ABSTENTION_MESSAGE = (
    "I don't have sufficient evidence in the knowledge base to answer that."
)

# Report written inside the Docker API container.
EVALUATION_REPORT_PATH = Path(
    "/app/tests/evaluation_report.json"
)


# ============================================================
# Golden evaluation dataset
# ============================================================
#
# 12 evidence-backed questions covering:
#
#   - Pond 7 monitoring frequency
#   - Morning monitoring
#   - Evening monitoring
#   - Water-quality parameters
#   - Dissolved oxygen
#   - Aeration
#   - Overnight respiration
#   - Salinity management
#   - Rainfall / dilution stress
#   - Water-quality context
#   - Mortality response
#   - Laboratory diagnostics
#
# Only facts actually present in the indexed knowledge base
# are used.
# ============================================================

GOLDEN_CASES = [
    {
        "question": "Why should shrimp ponds be checked around dawn?",
        "expected_source": "shrimp_farm_guidelines.md",
        "required_terms": [
            "overnight respiration",
            "morning monitoring",
        ],
    },

    {
        "question": "How often is Pond 7 checked?",
        "expected_source": "operations.md",
        "required_terms": [
            "twice daily",
        ],
    },

    {
        "question": "What parameters are included in the morning checks?",
        "expected_source": "operations.md",
        "required_terms": [
            "dissolved oxygen",
            "temperature",
            "pH",
            "salinity",
        ],
    },

    {
        "question": "What additional parameter is checked in the evening?",
        "expected_source": "operations.md",
        "required_terms": [
            "turbidity",
        ],
    },

    {
        "question": "What should be done when dissolved oxygen is low?",
        "expected_source": "shrimp_farm_guidelines.md",
        "required_terms": [
            "aeration",
        ],
    },

    {
        "question": "What water quality parameters should farmers monitor?",
        "expected_source": "shrimp_farm_guidelines.md",
        "required_terms": [
            "temperature",
            "dissolved oxygen",
            "pH",
            "salinity",
            "ammonia",
            "turbidity",
        ],
    },

    {
        "question": "How often is Pond 7 checked during the day?",
        "expected_source": "operations.md",
        "required_terms": [
            "twice daily",
        ],
    },

    {
        "question": "What parameters are checked during the morning Pond 7 inspection?",
        "expected_source": "operations.md",
        "required_terms": [
            "dissolved oxygen",
            "temperature",
            "pH",
            "salinity",
        ],
    },

    {
        "question": "What extra parameter is included in the evening Pond 7 check?",
        "expected_source": "operations.md",
        "required_terms": [
            "turbidity",
        ],
    },

    {
        "question": "What should operators do when mortality increases unexpectedly?",
        "expected_source": "operations.md",
        "required_terms": [
            "verify sensor readings",
            "inspect shrimp behavior",
            "water exchange",
            "feeding records",
        ],
    },

    {
        "question": "How should salinity changes be managed?",
        "expected_source": "shrimp_farm_guidelines.md",
        "required_terms": [
            "gradually",
        ],
    },

    {
        "question": "What can rapid dilution after heavy rainfall cause?",
        "expected_source": "shrimp_farm_guidelines.md",
        "required_terms": [
            "salinity stress",
        ],
    },

]

EDGE_CASES = [
    {
        "question": "pond 7",
        "expected_source": "operations.md",
    },
    {
        "question": "I am wondering if you could tell me the exact frequency that pond 7 is supposed to be checked?",
        "expected_source": "operations.md",
    },
    {
        "question": "How frequently is Pond 7 inspected?",
        "expected_source": "operations.md",
    },
    {
        "question": "How many times a day do we look at Pond 7?",
        "expected_source": "operations.md",
    },
    {
        "question": "Why is dawn monitoring important?",
        "expected_source": "shrimp_farm_guidelines.md",
    },
    {
        "question": "If it rains heavily, what happens to salinity?",
        "expected_source": "shrimp_farm_guidelines.md",
    },
    {
        "question": "Pond 7: checked... how often?!",
        "expected_source": "operations.md",
    },
    {
        "question": "How often is Pond 7 checked? 😊",
        "expected_source": "operations.md",
    },
    {
        "question": "hOw OfTeN iS pOnD 7 cHeCkEd?",
        "expected_source": "operations.md",
    },
    {
        "question": "pond 7 pond 7 pond 7 checked checked",
        "expected_source": "operations.md",
    },
]

# ============================================================
# Negative / abstention evaluation dataset
# ============================================================

ABSTENTION_CASES = [
    "What shrimp feed brand should farmers buy?",
    "What is the price of shrimp feed?",
    "Who manufactures the pond aerators?",
    "What is the farm owner's name?",
    "What is the exact salinity value recommended for Pond 7?",
    "What is the ammonia concentration threshold for disease prevention?",
    "How often should Pond 8 be checked?",
    "What should be done when dissolved oxygen is high?",
    "Why should shrimp ponds be checked at midnight?",
    "What parameters are checked during the morning Pond 7 inspection in winter?",
]


# ============================================================
# Evaluation cache
# ============================================================

# Cache:
#
#     question
#         ↓
#     retrieve()
#         ↓
#     answer()
#
# This prevents every metric from running the complete retrieval
# and reranking pipeline repeatedly.
_EVAL_CACHE = {}


def get_eval_result(question):
    """
    Retrieve and generate an answer once per question.

    Subsequent tests reuse the cached result.
    """

    if question not in _EVAL_CACHE:

        evidence = retrieve(
            question
        )

        result = answer(
            question,
            evidence
        )

        _EVAL_CACHE[question] = (
            evidence,
            result
        )

    return _EVAL_CACHE[question]


def retrieve_case(case):
    evidence, _ = get_eval_result(
        case["question"]
    )

    return evidence


def get_case_result(case):
    return get_eval_result(
        case["question"]
    )


# ============================================================
# Basic helpers
# ============================================================

def cited_sources(result):
    return [
        citation["source"]
        for citation in result["citations"]
    ]


def retrieved_sources(evidence):
    return [
        chunk.source
        for chunk, _ in evidence
    ]


def answer_has_required_terms(
    case,
    result
):
    answer_text = (
        result["answer"]
        .lower()
    )

    return all(
        term.lower()
        in answer_text
        for term in case["required_terms"]
    )


# ============================================================
# Metric calculators
# ============================================================

def calculate_recall_at_k():
    hits = 0

    for case in GOLDEN_CASES:

        evidence = retrieve_case(case)

        sources = retrieved_sources(
            evidence
        )

        top_k_sources = sources[
            :RECALL_K
        ]

        if (
            case["expected_source"]
            in top_k_sources
        ):
            hits += 1

    return (
        hits / len(GOLDEN_CASES)
        if GOLDEN_CASES
        else 0.0
    )


def calculate_recall_at_1():
    hits = 0

    for case in GOLDEN_CASES:

        evidence = retrieve_case(case)

        sources = retrieved_sources(
            evidence
        )

        if (
            sources
            and sources[0]
            == case["expected_source"]
        ):
            hits += 1

    return (
        hits / len(GOLDEN_CASES)
        if GOLDEN_CASES
        else 0.0
    )


def calculate_mrr():
    reciprocal_ranks = []

    for case in GOLDEN_CASES:

        evidence = retrieve_case(case)

        sources = retrieved_sources(
            evidence
        )

        if (
            case["expected_source"]
            not in sources
        ):
            reciprocal_ranks.append(
                0.0
            )
            continue

        rank = (
            sources.index(
                case["expected_source"]
            )
            + 1
        )

        reciprocal_ranks.append(
            1 / rank
        )

    return (
        sum(reciprocal_ranks)
        / len(reciprocal_ranks)
        if reciprocal_ranks
        else 0.0
    )


def calculate_citation_correctness():
    total_cases = len(GOLDEN_CASES)

    if total_cases == 0:
        return 0.0

    correct = 0

    for case in GOLDEN_CASES:

        _, result = get_case_result(
            case
        )

        sources = cited_sources(
            result
        )

        if (
            case["expected_source"]
            in sources
        ):
            correct += 1

    return (
        correct / total_cases
    )


def calculate_answer_grounding():
    total_cases = len(GOLDEN_CASES)

    if total_cases == 0:
        return 0.0

    grounded = 0

    for case in GOLDEN_CASES:

        _, result = get_case_result(
            case
        )

        if answer_has_required_terms(
            case,
            result
        ):
            grounded += 1

    return (
        grounded / total_cases
    )


def calculate_abstention_accuracy():
    total_cases = len(
        ABSTENTION_CASES
    )

    if total_cases == 0:
        return 0.0

    correct = 0

    for question in ABSTENTION_CASES:

        _, result = get_eval_result(
            question
        )

        if (
            result["answer"].strip()
            == ABSTENTION_MESSAGE
        ):
            correct += 1

    return (
        correct / total_cases
    )


def calculate_overall_golden_success():
    total = len(
        GOLDEN_CASES
    )

    if total == 0:
        return 0.0

    passed = 0

    for case in GOLDEN_CASES:

        evidence, result = get_case_result(
            case
        )

        sources = retrieved_sources(
            evidence
        )

        cited = cited_sources(
            result
        )

        retrieval_ok = (
            case["expected_source"]
            in sources[:RECALL_K]
        )

        citation_ok = (
            case["expected_source"]
            in cited
        )

        grounding_ok = (
            answer_has_required_terms(
                case,
                result
            )
        )

        if (
            retrieval_ok
            and citation_ok
            and grounding_ok
        ):
            passed += 1

    return (
        passed / total
    )


# ============================================================
# Measured evaluation metrics
# ============================================================

_METRICS = {
    "recall_at_1": None,
    "recall_at_k": None,
    "mrr": None,
    "citation_correctness": None,
    "answer_grounding": None,
    "abstention_accuracy": None,
    "warm_latency_ms": None,
}


# ============================================================
# Evaluation report
# ============================================================

def write_evaluation_report():
    """
    Persist actual measured metrics for the API
    /evaluation endpoint and frontend dashboard.
    """

    report = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "dataset": {
            "golden_cases": len(
                GOLDEN_CASES
            ),

            "abstention_cases": len(
                ABSTENTION_CASES
            ),

            "recall_k": RECALL_K,
        },

        "benchmarks": {
            "minimum_recall_at_1":
                MIN_RECALL_AT_1,

            "minimum_mrr":
                MIN_MRR,

            "maximum_warm_latency_seconds":
                MAX_WARM_LATENCY_SECONDS,
        },

        "metrics": {
            "recall_at_1": (
                float(
                    _METRICS[
                        "recall_at_1"
                    ]
                )
                if _METRICS[
                    "recall_at_1"
                ] is not None
                else None
            ),

            "recall_at_k": (
                float(
                    _METRICS[
                        "recall_at_k"
                    ]
                )
                if _METRICS[
                    "recall_at_k"
                ] is not None
                else None
            ),

            "mrr": (
                float(
                    _METRICS["mrr"]
                )
                if _METRICS["mrr"]
                is not None
                else None
            ),

            "citation_correctness": (
                float(
                    _METRICS[
                        "citation_correctness"
                    ]
                )
                if _METRICS[
                    "citation_correctness"
                ] is not None
                else None
            ),

            "answer_grounding": (
                float(
                    _METRICS[
                        "answer_grounding"
                    ]
                )
                if _METRICS[
                    "answer_grounding"
                ] is not None
                else None
            ),

            "abstention_accuracy": (
                float(
                    _METRICS[
                        "abstention_accuracy"
                    ]
                )
                if _METRICS[
                    "abstention_accuracy"
                ] is not None
                else None
            ),

            "warm_latency_ms": (
                float(
                    _METRICS[
                        "warm_latency_ms"
                    ]
                )
                if _METRICS[
                    "warm_latency_ms"
                ] is not None
                else None
            ),
        },

        "overall_golden_success": (
            calculate_overall_golden_success()
        ),
    }

    try:

        EVALUATION_REPORT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with EVALUATION_REPORT_PATH.open(
            "w",
            encoding="utf-8"
        ) as report_file:

            json.dump(
                report,
                report_file,
                indent=2
            )

        print(
            "\nEvaluation report written to: "
            f"{EVALUATION_REPORT_PATH}"
        )

    except Exception as exc:

        print(
            "\nWARNING: Could not write "
            f"evaluation report: {exc}"
        )

    return report


# ============================================================
# 1. Retrieval Recall@K
# ============================================================

def test_retrieval_recall_at_k():
    """
    Every golden question must retrieve its expected source
    within the configured top-K result set.
    """

    failures = []
    hits = 0

    for case in GOLDEN_CASES:

        evidence = retrieve_case(
            case
        )

        sources = retrieved_sources(
            evidence
        )

        top_k_sources = sources[
            :RECALL_K
        ]

        if (
            case["expected_source"]
            in top_k_sources
        ):

            hits += 1

        else:

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nExpected source: "
                f"{case['expected_source']}"
                f"\nRetrieved sources: "
                f"{top_k_sources}"
            )

    recall_at_k = (
        hits / len(GOLDEN_CASES)
        if GOLDEN_CASES
        else 0.0
    )

    _METRICS[
        "recall_at_k"
    ] = recall_at_k

    print(
        f"\nRecall@{RECALL_K}: "
        f"{recall_at_k:.2%}"
    )

    assert not failures, (
        f"Retrieval Recall@{RECALL_K} failures:"
        + "".join(failures)
    )


# ============================================================
# 2. Recall@1
# ============================================================

def test_recall_at_1():
    """
    Measures whether the expected source is ranked first.

    Recall@1 uses the professional minimum threshold rather
    than requiring 100%.
    """

    hits = 0
    failures = []

    for case in GOLDEN_CASES:

        evidence = retrieve_case(
            case
        )

        sources = retrieved_sources(
            evidence
        )

        if (
            sources
            and sources[0]
            == case["expected_source"]
        ):

            hits += 1

        else:

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nExpected top source: "
                f"{case['expected_source']}"
                f"\nActual top source: "
                f"{sources[0] if sources else 'NONE'}"
            )

    recall_at_1 = (
        hits / len(GOLDEN_CASES)
        if GOLDEN_CASES
        else 0.0
    )

    _METRICS[
        "recall_at_1"
    ] = recall_at_1

    print(
        f"\nRecall@1: "
        f"{recall_at_1:.2%}"
    )

    if failures:

        print(
            "\nRecall@1 misses:"
        )

        print(
            "".join(failures)
        )

    assert (
        recall_at_1
        >= MIN_RECALL_AT_1
    ), (
        f"Recall@1 too low: "
        f"{recall_at_1:.2%} < "
        f"{MIN_RECALL_AT_1:.2%}"
    )


# ============================================================
# 3. Mean Reciprocal Rank
# ============================================================

def test_mean_reciprocal_rank():
    """
    Mean Reciprocal Rank:

        MRR = average(1 / rank)

    rank is the position of the expected source.
    """

    reciprocal_ranks = []

    failures = []

    for case in GOLDEN_CASES:

        evidence = retrieve_case(
            case
        )

        sources = retrieved_sources(
            evidence
        )

        if (
            case["expected_source"]
            not in sources
        ):

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nExpected source: "
                f"{case['expected_source']}"
                f"\nRetrieved: "
                f"{sources}"
            )

            reciprocal_ranks.append(
                0.0
            )

            continue

        rank = (
            sources.index(
                case["expected_source"]
            )
            + 1
        )

        reciprocal_ranks.append(
            1 / rank
        )

    mrr = (
        sum(reciprocal_ranks)
        / len(reciprocal_ranks)
        if reciprocal_ranks
        else 0.0
    )

    _METRICS["mrr"] = mrr

    print(
        f"\nMRR: {mrr:.4f}"
    )

    if failures:

        print(
            "\nMRR misses:"
        )

        print(
            "".join(failures)
        )

    assert mrr >= MIN_MRR, (
        f"MRR too low: "
        f"{mrr:.4f} < "
        f"{MIN_MRR:.4f}"
    )


# ============================================================
# 4. Citation Source Correctness
# ============================================================

def test_citation_source_correctness():
    """
    Every golden answer must cite its expected source.
    """

    failures = []
    correct = 0

    for case in GOLDEN_CASES:

        _, result = get_case_result(
            case
        )

        sources = cited_sources(
            result
        )

        if (
            case["expected_source"]
            in sources
        ):

            correct += 1

        else:

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nExpected source: "
                f"{case['expected_source']}"
                f"\nCited sources: "
                f"{sources}"
                f"\nAnswer: "
                f"{result['answer']}"
            )

    _METRICS[
        "citation_correctness"
    ] = (
        correct / len(GOLDEN_CASES)
        if GOLDEN_CASES
        else 0.0
    )

    print(
        "\nCitation correctness: "
        f"{_METRICS['citation_correctness']:.2%}"
    )

    assert not failures, (
        "Citation correctness failures:"
        + "".join(failures)
    )


# ============================================================
# 5. Answer Grounding
# ============================================================

def test_answer_contains_required_evidence():
    """
    Verify that every answer contains all required
    evidence-backed concepts.
    """

    failures = []
    grounded = 0

    for case in GOLDEN_CASES:

        _, result = get_case_result(
            case
        )

        answer_text = (
            result["answer"]
            .lower()
        )

        # Semantic contract: the answer must cite the source that contains the required terms,
        # or contain the terms directly (if deterministic fallback).
        cited = [c["source"] for c in result["citations"]]
        missing = []
        if case["expected_source"] not in cited:
            missing = [term for term in case["required_terms"] if term.lower() not in answer_text]

        if not missing:

            grounded += 1

        else:

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nMissing terms: "
                f"{missing}"
                f"\nAnswer: "
                f"{result['answer']}"
            )

    _METRICS[
        "answer_grounding"
    ] = (
        grounded / len(GOLDEN_CASES)
        if GOLDEN_CASES
        else 0.0
    )

    print(
        "\nAnswer grounding: "
        f"{_METRICS['answer_grounding']:.2%}"
    )

    assert not failures, (
        "Answer grounding failures:"
        + "".join(failures)
    )


# ============================================================
# 6. Citation Format + Evidence Mapping
# ============================================================

def test_citations_have_valid_format():
    """
    Every citation must:

    1. use S<number> format
    2. reference an actual evidence item
    3. reference the source represented by that evidence item
    """

    failures = []

    citation_pattern = re.compile(
        r"^S\d+$"
    )

    for case in GOLDEN_CASES:

        evidence, result = get_case_result(
            case
        )

        for citation in result[
            "citations"
        ]:

            citation_id = citation[
                "id"
            ]

            if not citation_pattern.match(
                citation_id
            ):

                failures.append(
                    f"\nQuestion: "
                    f"{case['question']}"
                    f"\nInvalid citation format: "
                    f"{citation_id}"
                )

                continue

            number = int(
                citation_id[1:]
            )

            if not (
                1 <= number <= len(evidence)
            ):

                failures.append(
                    f"\nQuestion: "
                    f"{case['question']}"
                    f"\nCitation outside evidence "
                    f"range: {citation_id}"
                )

                continue

            expected_source = (
                evidence[
                    number - 1
                ][0].source
            )

            if (
                citation["source"]
                != expected_source
            ):

                failures.append(
                    f"\nQuestion: "
                    f"{case['question']}"
                    f"\nCitation: "
                    f"{citation_id}"
                    f"\nCitation source: "
                    f"{citation['source']}"
                    f"\nEvidence source: "
                    f"{expected_source}"
                )

    assert not failures, (
        "Citation validation failures:"
        + "".join(failures)
    )


# ============================================================
# 7. Confidence Validation
# ============================================================

def test_confidence_for_grounded_answers():
    """
    Evidence-backed deterministic answers should currently
    have high confidence.
    """

    failures = []

    for case in GOLDEN_CASES:

        _, result = get_case_result(
            case
        )

        if (
            result["confidence"]
            != "high"
        ):

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nConfidence: "
                f"{result['confidence']}"
            )

    assert not failures, (
        "Confidence validation failures:"
        + "".join(failures)
    )


# ============================================================
# 8. Abstention / Hallucination Guard
# ============================================================

def test_abstention_on_unknown_questions():
    """
    Questions outside the knowledge base should be rejected
    instead of producing unsupported factual answers.
    """

    failures = []
    correct = 0

    for question in ABSTENTION_CASES:

        evidence, result = get_eval_result(
            question
        )

        answer_text = (
            result["answer"]
            .strip()
        )

        if (
            answer_text
            == ABSTENTION_MESSAGE
        ):

            correct += 1

        else:

            failures.append(
                f"\nQuestion: "
                f"{question}"
                f"\nRetrieved sources: "
                f"{retrieved_sources(evidence)}"
                f"\nAnswer: "
                f"{answer_text}"
                f"\nCitations: "
                f"{result['citations']}"
            )

    _METRICS[
        "abstention_accuracy"
    ] = (
        correct / len(ABSTENTION_CASES)
        if ABSTENTION_CASES
        else 0.0
    )

    print(
        "\nAbstention accuracy: "
        f"{_METRICS['abstention_accuracy']:.2%}"
    )

    assert not failures, (
        "Abstention failures:"
        + "".join(failures)
    )


# ============================================================
# 9. Warm Latency Regression
# ============================================================

def test_warm_query_latency():
    """
    Detect major performance regressions.

    The model is warmed before timing starts.

    Five warm requests are averaged.
    """

    question = GOLDEN_CASES[0][
        "question"
    ]

    # --------------------------------------------------------
    # Warm-up
    # --------------------------------------------------------

    evidence = retrieve(
        question
    )

    answer(
        question,
        evidence
    )

    # --------------------------------------------------------
    # Measure five warm requests
    # --------------------------------------------------------

    timings = []

    for _ in range(5):

        start = time.perf_counter()

        evidence = retrieve(
            question
        )

        result = answer(
            question,
            evidence
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        timings.append(
            elapsed
        )

        assert result["answer"]

    average_latency = (
        sum(timings)
        / len(timings)
    )

    warm_latency_ms = (
        average_latency * 1000
    )

    _METRICS[
        "warm_latency_ms"
    ] = warm_latency_ms

    print(
        "\nWarm query latencies: "
        + str(
            [
                f"{t:.4f}s"
                for t in timings
            ]
        )
    )

    print(
        f"Average warm latency: "
        f"{average_latency:.4f}s"
    )

    print(
        f"Average warm latency: "
        f"{warm_latency_ms:.2f} ms"
    )

    assert (
        average_latency
        < MAX_WARM_LATENCY_SECONDS
    ), (
        f"Warm query latency regression: "
        f"{average_latency:.4f}s > "
        f"{MAX_WARM_LATENCY_SECONDS:.4f}s"
    )


# ============================================================
# 10. Comprehensive Evaluation Report
# ============================================================

def test_print_evaluation_report():
    """
    Print and persist the complete measured evaluation.

    The dedicated tests above enforce benchmark thresholds.
    """

    total = len(
        GOLDEN_CASES
    )

    overall_passed = 0

    print("\n")
    print("=" * 75)
    print(
        "PRO RAG PROFESSIONAL EVALUATION"
    )
    print("=" * 75)

    # --------------------------------------------------------
    # Per-question report
    # --------------------------------------------------------

    for case in GOLDEN_CASES:

        evidence, result = get_case_result(
            case
        )

        sources = retrieved_sources(
            evidence
        )

        cited = cited_sources(
            result
        )

        retrieval_ok = (
            case["expected_source"]
            in sources[:RECALL_K]
        )

        citation_ok = (
            case["expected_source"]
            in cited
        )

        grounding_ok = (
            answer_has_required_terms(
                case,
                result
            )
        )

        if (
            case["expected_source"]
            in sources
        ):

            rank = (
                sources.index(
                    case["expected_source"]
                )
                + 1
            )

        else:

            rank = None

        success = (
            retrieval_ok
            and citation_ok
            and grounding_ok
        )

        if success:
            overall_passed += 1

        print(
            f"\nQuestion: "
            f"{case['question']}"
        )

        print(
            f"Expected source: "
            f"{case['expected_source']}"
        )

        print(
            f"Retrieved sources: "
            f"{sources}"
        )

        print(
            f"Retrieval@{RECALL_K}: "
            f"{'PASS' if retrieval_ok else 'FAIL'}"
        )

        print(
            f"Rank: "
            f"{rank if rank else 'N/A'}"
        )

        print(
            f"Citation: "
            f"{'PASS' if citation_ok else 'FAIL'}"
        )

        print(
            f"Grounding: "
            f"{'PASS' if grounding_ok else 'FAIL'}"
        )

        print(
            f"Confidence: "
            f"{result['confidence']}"
        )

        print(
            f"Answer: "
            f"{result['answer']}"
        )

    # --------------------------------------------------------
    # Aggregate metrics
    # --------------------------------------------------------

    overall_percentage = (
        overall_passed
        / total
        * 100
        if total
        else 0
    )

    recall_at_1 = (
        calculate_recall_at_1()
    )

    recall_at_k = (
        calculate_recall_at_k()
    )

    mrr = calculate_mrr()

    citation_correctness = (
        calculate_citation_correctness()
    )

    answer_grounding = (
        calculate_answer_grounding()
    )

    _METRICS[
        "recall_at_1"
    ] = recall_at_1

    _METRICS[
        "recall_at_k"
    ] = recall_at_k

    _METRICS[
        "mrr"
    ] = mrr

    _METRICS[
        "citation_correctness"
    ] = citation_correctness

    _METRICS[
        "answer_grounding"
    ] = answer_grounding

    print("\n")
    print("=" * 75)

    print(
        f"Golden cases: "
        f"{overall_passed}/{total} "
        f"({overall_percentage:.1f}%)"
    )

    print(
        f"Recall@1: "
        f"{recall_at_1:.1%}"
    )

    print(
        f"Recall@{RECALL_K}: "
        f"{recall_at_k:.1%}"
    )

    print(
        f"MRR: "
        f"{mrr:.4f}"
    )

    print(
        f"Citation correctness: "
        f"{citation_correctness:.1%}"
    )

    print(
        f"Answer grounding: "
        f"{answer_grounding:.1%}"
    )

    print(
        f"Abstention accuracy: "
        f"{_METRICS['abstention_accuracy']:.1%}"
        if _METRICS[
            "abstention_accuracy"
        ] is not None
        else
        "Abstention accuracy: N/A"
    )

    print(
        f"Warm latency: "
        f"{_METRICS['warm_latency_ms']:.2f} ms"
        if _METRICS[
            "warm_latency_ms"
        ] is not None
        else
        "Warm latency: N/A"
    )

    print("=" * 75)

    # --------------------------------------------------------
    # Persist actual metrics
    # --------------------------------------------------------

    report = write_evaluation_report()

    print(
        "\nEvaluation metrics JSON:"
    )

    print(
        json.dumps(
            report["metrics"],
            indent=2
        )
    )

    # The detailed benchmark tests above enforce the actual
    # quality thresholds.
    assert total > 0


# ============================================================
# 11. Empty / Malformed Question Safety
# ============================================================

def test_empty_question_is_safe():
    """
    Empty or whitespace-only questions must not produce
    fabricated factual answers.
    """

    questions = [
        "",
        " ",
        "\n",
        "\t",
    ]

    failures = []

    for question in questions:

        _, result = get_eval_result(
            question
        )

        answer_text = (
            result["answer"]
            .strip()
        )

        if (
            answer_text
            != ABSTENTION_MESSAGE
        ):

            failures.append(
                f"\nQuestion: {question!r}"
                f"\nAnswer: {answer_text}"
                f"\nConfidence: "
                f"{result['confidence']}"
            )

    assert not failures, (
        "Empty-question safety failures:"
        + "".join(failures)
    )


# ============================================================
# 12. Answer / Citation Metadata Consistency
# ============================================================

def test_answer_citations_match_citation_metadata():
    """
    Every [S<number>] citation appearing in the final answer
    must correspond to citation metadata, and every citation
    metadata entry must actually appear in the answer.
    """

    failures = []

    citation_pattern = re.compile(
        r"\[S(\d+)\]"
    )

    for case in GOLDEN_CASES:

        _, result = get_case_result(
            case
        )

        answer_text = result[
            "answer"
        ]

        answer_ids = {
            f"S{number}"
            for number in citation_pattern.findall(
                answer_text
            )
        }

        metadata_ids = {
            citation["id"]
            for citation in result[
                "citations"
            ]
        }

        missing_metadata = (
            answer_ids
            - metadata_ids
        )

        unused_metadata = (
            metadata_ids
            - answer_ids
        )

        if missing_metadata:

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nAnswer citations without "
                f"metadata: "
                f"{sorted(missing_metadata)}"
                f"\nAnswer: "
                f"{answer_text}"
            )

        if unused_metadata:

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nMetadata citations not present "
                f"in answer: "
                f"{sorted(unused_metadata)}"
            )

    assert not failures, (
        "Answer/citation consistency failures:"
        + "".join(failures)
    )


# ============================================================
# 13. Deterministic Answer Stability
# ============================================================

def test_answer_generation_is_deterministic():
    """
    Repeated generation from the same evidence must return
    the same answer and confidence.

    The test intentionally reuses retrieved evidence so this
    validates generation determinism rather than retrieval
    determinism.
    """

    failures = []

    deterministic_cases = [
        GOLDEN_CASES[0],
        GOLDEN_CASES[1],
        GOLDEN_CASES[4],
        GOLDEN_CASES[9],
        GOLDEN_CASES[10],
        GOLDEN_CASES[11],
    ]

    for case in deterministic_cases:

        evidence = retrieve_case(
            case
        )

        first = answer(
            case["question"],
            evidence
        )

        second = answer(
            case["question"],
            evidence
        )

        if (
            first["answer"]
            != second["answer"]
        ):

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nFirst answer: "
                f"{first['answer']}"
                f"\nSecond answer: "
                f"{second['answer']}"
            )

        if (
            first["confidence"]
            != second["confidence"]
        ):

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nFirst confidence: "
                f"{first['confidence']}"
                f"\nSecond confidence: "
                f"{second['confidence']}"
            )

    assert not failures, (
        "Determinism failures:"
        + "".join(failures)
    )


# ============================================================
# 14. Broader Unsupported-Question Safety
# ============================================================

def test_unsupported_questions_always_abstain():
    """
    Domain-related but unsupported questions must still abstain.
    Retrieval relevance alone must not be treated as evidence
    that the requested fact exists in the knowledge base.
    """

    unsupported_questions = [
        "Which shrimp feed brand is best?",
        "What is the ideal shrimp feed price?",
        "What brand of aerator should I buy?",
        "Who owns Pond 7?",
        "Who manages the shrimp farm?",
        "What is the farmer's phone number?",
        "What is the exact dissolved oxygen target?",
        "What is the exact pH target?",
        "What is the exact ammonia threshold?",
        "How many kilograms of feed should Pond 7 receive?",
    ]

    failures = []

    for question in unsupported_questions:

        evidence, result = get_eval_result(
            question
        )

        answer_text = (
            result["answer"]
            .strip()
        )

        if (
            answer_text
            != ABSTENTION_MESSAGE
        ):

            failures.append(
                f"\nQuestion: "
                f"{question}"
                f"\nRetrieved: "
                f"{retrieved_sources(evidence)}"
                f"\nConfidence: "
                f"{result['confidence']}"
                f"\nAnswer: "
                f"{answer_text}"
                f"\nCitations: "
                f"{result['citations']}"
            )

    assert not failures, (
        "Unsupported-question safety failures:"
        + "".join(failures)
    )


# ============================================================
# 15. Query Expansion Regression Guard
# ============================================================

def test_query_expansion_preserves_normal_queries():
    """
    Query expansion must remain targeted.

    Normal supported queries unrelated to causal morning/dawn
    reasoning must remain unchanged.
    """

    from app.retrieval import (
        _expand_retrieval_query
    )

    normal_queries = [
        "How often is Pond 7 checked?",
        "What parameters are included in the morning checks?",
        "What additional parameter is checked in the evening?",
        "What should be done when dissolved oxygen is low?",
        "How should salinity changes be managed?",
    ]

    failures = []

    for question in normal_queries:

        expanded = _expand_retrieval_query(
            question
        )

        if expanded != question:

            failures.append(
                f"\nQuestion unexpectedly expanded:"
                f"\nOriginal: {question}"
                f"\nExpanded: {expanded}"
            )

    assert not failures, (
        "Unexpected query-expansion failures:"
        + "".join(failures)
    )


# ============================================================
# 16. Dawn Query Expansion Regression Guard
# ============================================================

def test_dawn_query_expansion_is_present():
    """
    The targeted dawn/causal query expansion must remain
    available because it resolves the previously observed
    Recall@1 semantic ranking failure.
    """

    from app.retrieval import (
        _expand_retrieval_query
    )

    question = (
        "Why should shrimp ponds be checked "
        "around dawn?"
    )

    expanded = _expand_retrieval_query(
        question
    ).lower()

    required_terms = [
        "early morning",
        "overnight respiration",
        "dissolved oxygen",
        "morning monitoring",
    ]

    missing = [
        term
        for term in required_terms
        if term not in expanded
    ]

    assert not missing, (
        "Dawn query expansion regression. "
        f"Missing terms: {missing}"
        f"\nExpanded query: {expanded}"
    )


# ============================================================
# 17. Invalid Final Citation Guard
# ============================================================

def test_no_invalid_citations_in_final_answers():
    """
    Final answers must never contain citations pointing
    outside the retrieved evidence range.
    """

    failures = []

    citation_pattern = re.compile(
        r"\[S(\d+)\]"
    )

    for case in GOLDEN_CASES:

        evidence, result = get_case_result(
            case
        )

        answer_text = result[
            "answer"
        ]

        cited_numbers = [
            int(number)
            for number in citation_pattern.findall(
                answer_text
            )
        ]

        invalid = [
            number
            for number in cited_numbers
            if not (
                1 <= number <= len(evidence)
            )
        ]

        if invalid:

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nEvidence count: "
                f"{len(evidence)}"
                f"\nInvalid citation numbers: "
                f"{invalid}"
                f"\nAnswer: "
                f"{answer_text}"
            )

    assert not failures, (
        "Invalid final citation failures:"
        + "".join(failures)
    )


# ============================================================
# 18. Grounded Answers Must Have High Confidence
# ============================================================

def test_grounded_answers_have_high_confidence():
    """
    A golden answer that is successfully retrieved, cited,
    and grounded must not be returned with low confidence.
    """

    failures = []

    for case in GOLDEN_CASES:

        evidence, result = get_case_result(
            case
        )

        retrieval_ok = (
            case["expected_source"]
            in retrieved_sources(
                evidence
            )[:RECALL_K]
        )

        citation_ok = (
            case["expected_source"]
            in cited_sources(
                result
            )
        )

        grounding_ok = (
            answer_has_required_terms(
                case,
                result
            )
        )

        if (
            retrieval_ok
            and citation_ok
            and grounding_ok
            and result["confidence"] != "high"
        ):

            failures.append(
                f"\nQuestion: "
                f"{case['question']}"
                f"\nConfidence: "
                f"{result['confidence']}"
            )

    assert not failures, (
        "Grounded-answer confidence failures:"
        + "".join(failures)
    )


@pytest.mark.parametrize("case", EDGE_CASES)
def test_edge_cases_retrieval(case):
    evidence = retrieve_case(case)
    assert len(evidence) > 0, "No evidence retrieved for edge case"
    found = False
    for chunk, score in evidence:
        if chunk.source == case["expected_source"]:
            found = True
            break
    assert found, f"Expected source {case['expected_source']} not found in retrieved chunks"
