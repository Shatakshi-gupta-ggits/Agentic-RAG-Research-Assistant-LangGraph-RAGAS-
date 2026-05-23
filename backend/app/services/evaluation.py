"""
RAGAS Evaluation Service
Evaluates RAG pipeline on faithfulness, answer relevancy, context precision.
"""
from typing import List, Dict
from datasets import Dataset


def evaluate_rag(
    questions: List[str],
    answers: List[str],
    contexts: List[List[str]],
    ground_truths: List[str] | None = None,
) -> Dict:
    """
    Run RAGAS evaluation.
    Returns a dict of metric_name → score.

    ground_truths is optional — if not provided, skips answer_correctness.
    """
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision

        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }
        if ground_truths:
            data["ground_truth"] = ground_truths

        dataset = Dataset.from_dict(data)
        metrics = [faithfulness, answer_relevancy, context_precision]

        result = evaluate(dataset, metrics=metrics)
        return {
            "faithfulness": round(float(result["faithfulness"]), 4),
            "answer_relevancy": round(float(result["answer_relevancy"]), 4),
            "context_precision": round(float(result["context_precision"]), 4),
        }
    except Exception as e:
        return {"error": str(e), "note": "RAGAS evaluation failed — check Ollama is running"}
