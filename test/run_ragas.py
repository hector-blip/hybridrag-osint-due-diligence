# run_ragas.py
import json
import math
import pandas as pd
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    LLMContextPrecisionWithoutReference,   # context_precision sans ground truth
    ResponseRelevancy,                      # remplace context_recall sans reference
)
from ragas.llms import LangchainLLMWrapper
from datasets import Dataset
from langchain_openai import ChatOpenAI
from retrievers import c1_vector_rag, c2_graph_rag, c3_hybrid_no_hitl, c4_hybrid_hitl
from questions_test import QUESTIONS

# Configuration du LLM pour RAGAS (méthode correcte pour ragas >= 0.1.x)
_openai_llm = ChatOpenAI(model="gpt-4o-mini")
ragas_llm   = LangchainLLMWrapper(_openai_llm)

context_precision_no_ref = LLMContextPrecisionWithoutReference()
response_relevancy       = ResponseRelevancy()

METRICS = [faithfulness, answer_relevancy, context_precision_no_ref, response_relevancy]
for m in METRICS:
    m.llm = ragas_llm

def safe_mean(values):
    """Moyenne d'une liste de scores, en ignorant les None/NaN."""
    valid = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return sum(valid) / len(valid) if valid else float('nan')


CONDITIONS = {
    "C1_VectorRAG"       : c1_vector_rag,
    "C2_GraphRAG"        : c2_graph_rag,
    "C3_Hybrid_noHITL"   : c3_hybrid_no_hitl,
    "C4_Hybrid_HITL"     : c4_hybrid_hitl,
}

# Aplatir les questions avec leur catégorie
all_questions = []
for cat, qs in QUESTIONS.items():
    for q in qs:
        all_questions.append({"question": q, "category": cat})

results_all = {}

for condition_name, rag_fn in CONDITIONS.items():
    print(f"\n{'='*50}")
    print(f"Condition : {condition_name}")
    print(f"{'='*50}")

    questions, answers, contexts_list, categories = [], [], [], []

    for item in all_questions:
        q   = item["question"]
        cat = item["category"]
        print(f"  [{cat}] {q[:60]}...")

        try:
            result = rag_fn(q)
            questions.append(q)
            answers.append(result["answer"])
            contexts_list.append(result["contexts"])
            categories.append(cat)
        except Exception as e:
            print(f"    ERREUR : {e}")
            questions.append(q)
            answers.append("ERREUR")
            contexts_list.append([""])
            categories.append(cat)

    # Construire le dataset RAGAS
    dataset = Dataset.from_dict({
        "question"  : questions,
        "answer"    : answers,
        "contexts"  : contexts_list,
    })

    # Évaluation RAGAS
    print(f"\nÉvaluation RAGAS pour {condition_name}...")
    scores = evaluate(
        dataset,
        metrics=METRICS,
    )

    # Clés réelles disponibles dans cet objet scores (varie selon version RAGAS)
    available_keys = list(scores.scores[0].keys()) if scores.scores else []
    print(f"  [DEBUG] clés disponibles : {available_keys}")

    # Construire avg dynamiquement via m.name → évite tout KeyError
    avg = {}
    for m in METRICS:
        key = m.name
        if key in available_keys:
            avg[key] = safe_mean([row.get(key) for row in scores.scores])
        else:
            print(f"  [WARN] métrique absente des résultats : {key}")
            avg[key] = float('nan')

    results_all[condition_name] = {
        "scores_moyens" : avg,
        "categories"    : categories,
        "questions"     : questions,
        "answers"       : answers,
    }

    for key, val in avg.items():
        print(f"  {key:<45}: {val:.3f}")

    # Export CSV par condition (scores bruts par question pour tests statistiques)
    scores_df = scores.to_pandas()
    scores_df["condition"] = condition_name
    scores_df["category"]  = categories
    csv_path = f'scores_{condition_name}.csv'
    scores_df.to_csv(csv_path, index=False)
    print(f"  → CSV exporté : {csv_path}")

# Sauvegarde des scores moyens globaux
with open('ragas_results.json', 'w', encoding='utf-8') as f:
    json.dump(
        {k: v["scores_moyens"] for k, v in results_all.items()},
        f, indent=2, ensure_ascii=False
    )

print("\n✅ Résultats sauvegardés dans ragas_results.json")
