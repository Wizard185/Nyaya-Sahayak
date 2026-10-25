
import csv
import json
import time
import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env before importing modules that read environment variables.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

from rag.retriever import get_retriever
from llm.generator import generate_answer


# Prefer cpa_retrieval_eval.json; fall back to the uploaded filename.
EVAL_FILE = BASE_DIR / "cpa_retrieval_eval.json"
if not EVAL_FILE.exists():
    EVAL_FILE = BASE_DIR / "cpa_retrieval_eval(1).json"

OUTPUT_FILE = BASE_DIR / "rag_eval_results.csv"
TOP_K = 6


def calculate_metrics(expected, retrieved):
    """Calculate section-retrieval metrics for one question."""
    expected = set(expected)
    retrieved = set(retrieved)

    relevant = expected & retrieved
    union = expected | retrieved

    precision = len(relevant) / len(retrieved) if retrieved else 0.0
    recall = len(relevant) / len(expected) if expected else 0.0

    # Jaccard similarity of expected and retrieved section sets.
    # This is NOT conventional classification accuracy.
    accuracy = len(relevant) / len(union) if union else 0.0

    # Per-question hit rate: did retrieval find at least one expected section?
    hitrate = 1.0 if relevant else 0.0

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "hitrate": hitrate,
        "true_positives": len(relevant),
        "false_positives": len(retrieved - expected),
        "false_negatives": len(expected - retrieved),
    }


def main():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(
            f"Evaluation JSON not found in: {BASE_DIR}\n"
            "Expected cpa_retrieval_eval.json or "
            "cpa_retrieval_eval(1).json."
        )

    # Fail early with a clear error if the embedding configuration is missing.
    if not os.getenv("OLLAMA_EMBED_MODEL"):
        raise EnvironmentError(
            "OLLAMA_EMBED_MODEL is missing. Check backend/.env."
        )

    with EVAL_FILE.open("r", encoding="utf-8") as f:
        test_cases = json.load(f)

    if not isinstance(test_cases, list):
        raise ValueError("Evaluation JSON must contain a list of test cases.")

    print(f"Evaluation file: {EVAL_FILE.name}")
    print(f"Embedding model: {os.getenv('OLLAMA_EMBED_MODEL')}")
    print(f"Top K: {TOP_K}\n")

    # Initialize once, outside the loop.
    retriever = get_retriever()
    rows = []

    total_tp = 0
    total_fp = 0
    total_fn = 0

    metric_totals = {
        "accuracy": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "hitrate": 0.0,
    }

    successful = 0

    for index, case in enumerate(test_cases, start=1):
        question_id = case.get("id", f"QUESTION_{index:03d}")
        question = case["question"]
        reference_answer = case.get("answer", "")
        expected_sections = case.get("reference_sections", [])

        print(f"[{index}/{len(test_cases)}] {question_id}")
        start = time.perf_counter()

        try:
            # Dense + BM25 + RRF retrieval, as implemented by your retriever.
            retrieved_chunks = retriever.search_acts(question, n=TOP_K)

            retrieved_sections = list(dict.fromkeys(
                chunk.get("section_id")
                for chunk in retrieved_chunks
                if chunk.get("section_id")
            ))

            # Generate an answer using the retrieved context.
            generated_answer = generate_answer(
                question,
                retrieved_chunks
            )

            elapsed = time.perf_counter() - start

            metrics = calculate_metrics(
                expected_sections,
                retrieved_sections
            )

            successful += 1

            for key in metric_totals:
                metric_totals[key] += metrics[key]

            total_tp += metrics["true_positives"]
            total_fp += metrics["false_positives"]
            total_fn += metrics["false_negatives"]

            print(
                f"  Accuracy (Jaccard)={metrics['accuracy']:.2f}, "
                f"Precision={metrics['precision']:.2f}, "
                f"Recall={metrics['recall']:.2f}, "
                f"Hit={metrics['hitrate']:.0f}, "
                f"Time={elapsed:.2f}s"
            )

            rows.append({
                "id": question_id,
                "question": question,
                "reference_answer": reference_answer,
                "generated_answer": generated_answer,
                "expected_sections": json.dumps(expected_sections),
                "retrieved_sections": json.dumps(retrieved_sections),
                "accuracy": round(metrics["accuracy"], 4),
                "precision": round(metrics["precision"], 4),
                "recall": round(metrics["recall"], 4),
                "hitrate": round(metrics["hitrate"], 4),
                "latency_seconds": round(elapsed, 3),
                "error": "",
                "answer_correctness_manual": "",
            })

        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(f"  ERROR: {exc}")

            rows.append({
                "id": question_id,
                "question": question,
                "reference_answer": reference_answer,
                "generated_answer": "",
                "expected_sections": json.dumps(expected_sections),
                "retrieved_sections": "[]",
                "accuracy": "",
                "precision": "",
                "recall": "",
                "hitrate": "",
                "latency_seconds": round(elapsed, 3),
                "error": str(exc),
                "answer_correctness_manual": "",
            })

    columns = [
        "id",
        "question",
        "reference_answer",
        "generated_answer",
        "expected_sections",
        "retrieved_sections",
        "accuracy",
        "precision",
        "recall",
        "hitrate",
        "latency_seconds",
        "error",
        "answer_correctness_manual",
    ]

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    failed = len(test_cases) - successful

    print("\n========== FINAL RESULTS ==========")
    print(f"Total questions:     {len(test_cases)}")
    print(f"Successful questions: {successful}")
    print(f"Failed questions:     {failed}")

    if successful:
        print("\nMacro-average retrieval metrics:")
        for key, total in metric_totals.items():
            print(f"{key.title()}: {total / successful:.4f}")

        micro_precision = (
            total_tp / (total_tp + total_fp)
            if total_tp + total_fp else 0.0
        )
        micro_recall = (
            total_tp / (total_tp + total_fn)
            if total_tp + total_fn else 0.0
        )

        print(f"\nMicro Precision: {micro_precision:.4f}")
        print(f"Micro Recall:    {micro_recall:.4f}")

    print(f"\nDetailed results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
