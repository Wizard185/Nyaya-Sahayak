
import csv
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

from rag.retriever import get_retriever
from llm.generator import generate_answer

EVAL_FILE = BASE_DIR / "cpa_scenario_eval.json"
# cpa_scenario_eval.json
# cpa_retrieval_eval.json

if not EVAL_FILE.exists():
    EVAL_FILE = BASE_DIR / "cpa_retrieval_eval.json"

OUTPUT_FILE = BASE_DIR / "rag_eval_results.csv"
TOP_K = 6

# Number of questions to evaluate
NUM_QUESTIONS = 2  # Set to None to evaluate all questions


def calculate_metrics(expected, retrieved):
    expected = set(expected)
    retrieved = set(retrieved)

    relevant = expected & retrieved
    union = expected | retrieved

    precision = len(relevant) / len(retrieved) if retrieved else 0.0
    recall = len(relevant) / len(expected) if expected else 0.0
    accuracy = len(relevant) / len(union) if union else 0.0
    hitrate = 1.0 if relevant else 0.0

    TP = len(relevant)
    FP = len(retrieved - expected)
    FN = len(expected - retrieved)

    return accuracy, precision, recall, hitrate, TP, FP, FN


def main():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Evaluation file not found: {EVAL_FILE}")

    if not os.getenv("OLLAMA_EMBED_MODEL"):
        raise EnvironmentError("OLLAMA_EMBED_MODEL is not set in .env")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    if not isinstance(test_cases, list):
        raise ValueError("Evaluation JSON must contain a list of test cases")

    # Select the requested number of questions
    if NUM_QUESTIONS is not None:
        if NUM_QUESTIONS < 1:
            raise ValueError("NUM_QUESTIONS must be at least 1 or None")
        test_cases = test_cases[:NUM_QUESTIONS]

    if not test_cases:
        raise ValueError("No test cases found in the evaluation file")

    print(f"Evaluation file: {EVAL_FILE}")
    print(f"Embedding model: {os.getenv('OLLAMA_EMBED_MODEL')}")
    print(f"TOP_K: {TOP_K}")
    print(f"Questions to evaluate: {len(test_cases)}")

    retriever = get_retriever()

    results = []
    total_tp = 0
    total_fp = 0
    total_fn = 0
    successful = 0
    failed = 0

    for i, case in enumerate(test_cases, start=1):
        case_id = case.get("id", f"CASE_{i}")
        question = case.get("question", "")
        expected_sections = case.get("reference_sections", [])

        print(f"\n[{i}/{len(test_cases)}] Evaluating {case_id}")

        try:
            start_time = time.time()

            retrieved_chunks = retriever.search_acts(question, n=TOP_K)

            retrieved_sections = [
                chunk.get("section_id")
                for chunk in retrieved_chunks
                if chunk.get("section_id")
            ]

            answer = generate_answer(
                query=question,
                act_chunks=retrieved_chunks,
                language="en"
            )

            elapsed_time = time.time() - start_time

            accuracy, precision, recall, hitrate, TP, FP, FN = (
                calculate_metrics(expected_sections, retrieved_sections)
            )

            total_tp += TP
            total_fp += FP
            total_fn += FN
            successful += 1

            results.append({
                "id": case_id,
                "question": question,
                "expected_sections": "|".join(expected_sections),
                "retrieved_sections": "|".join(retrieved_sections),
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "hitrate": hitrate,
                "TP": TP,
                "FP": FP,
                "FN": FN,
                "answer": answer,
                "time_seconds": round(elapsed_time, 2),
                "status": "success"
            })

            print(
                f"Accuracy: {accuracy:.3f} | "
                f"Precision: {precision:.3f} | "
                f"Recall: {recall:.3f} | "
                f"Hit Rate: {hitrate:.3f}"
            )

        except Exception as e:
            failed += 1
            print(f"Error evaluating {case_id}: {e}")

            results.append({
                "id": case_id,
                "question": question,
                "expected_sections": "|".join(expected_sections),
                "retrieved_sections": "",
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "hitrate": 0.0,
                "TP": 0,
                "FP": 0,
                "FN": 0,
                "answer": "",
                "time_seconds": 0.0,
                "status": f"failed: {e}"
            })

    fieldnames = [
        "id",
        "question",
        "expected_sections",
        "retrieved_sections",
        "accuracy",
        "precision",
        "recall",
        "hitrate",
        "TP",
        "FP",
        "FN",
        "answer",
        "time_seconds",
        "status"
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    successful_results = [
        r for r in results if r["status"] == "success"
    ]

    if successful_results:
        count = len(successful_results)

        macro_accuracy = sum(
            r["accuracy"] for r in successful_results
        ) / count

        macro_precision = sum(
            r["precision"] for r in successful_results
        ) / count

        macro_recall = sum(
            r["recall"] for r in successful_results
        ) / count

        macro_hitrate = sum(
            r["hitrate"] for r in successful_results
        ) / count

        micro_precision = (
            total_tp / (total_tp + total_fp)
            if total_tp + total_fp else 0.0
        )

        micro_recall = (
            total_tp / (total_tp + total_fn)
            if total_tp + total_fn else 0.0
        )

        print("\n========== EVALUATION SUMMARY ==========")
        print(f"Questions selected: {len(test_cases)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Macro Accuracy: {macro_accuracy:.3f}")
        print(f"Macro Precision: {macro_precision:.3f}")
        print(f"Macro Recall: {macro_recall:.3f}")
        print(f"Macro Hit Rate: {macro_hitrate:.3f}")
        print(f"Micro Precision: {micro_precision:.3f}")
        print(f"Micro Recall: {micro_recall:.3f}")
        print(f"Results saved to: {OUTPUT_FILE}")
    else:
        print("\nNo questions were evaluated successfully.")
        print(f"Failed: {failed}")
        print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
