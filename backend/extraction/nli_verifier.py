from transformers import pipeline
import sys

# We keep the model loaded globally to avoid reloading on every request
_nli_pipeline = None

def init_nli_model():
    global _nli_pipeline
    if _nli_pipeline is None:
        print("Initialisation du modèle mathématique NLI (DeBERTa-v3)... Cela peut prendre quelques secondes...")
        # top_k=None forces the pipeline to return scores for all classes (contradiction, entailment, neutral)
        _nli_pipeline = pipeline("text-classification", model="cross-encoder/nli-deberta-v3-small", top_k=None)
        print("Modèle NLI chargé avec succès !")

def calculate_nli_confidence(abstract: str, subject: str, relation: str, obj: str) -> float:
    """
    Calcule la probabilité mathématique (Softmax) que l'Abstract (Prémisse) prouve
    le Triplet (Hypothèse) à l'aide d'un Cross-Encoder NLI.
    """
    global _nli_pipeline
    if _nli_pipeline is None:
        init_nli_model()

    # Le modèle DeBERTa est anglophone. Si la relation est en français (ex: "AFFILIÉ_À"),
    # il risque de ne pas comprendre et de répondre "Neutral" (score très bas).
    # On traduit donc dynamiquement les relations métiers pour l'hypothèse :
    relation_map = {
        "AFFILIÉ_À": "is officially affiliated with or works for",
        "A_POUR_EXPERTISE": "has demonstrated specific research expertise in",
        "A_ECRIT": "is the author of research concerning"
    }
    english_relation = relation_map.get(relation, f"is related to ({relation})")

    hypothesis = f"Based on the text, {subject} {english_relation} {obj}."

    inputs = {"text": abstract, "text_pair": hypothesis}

    try:
        # Le pipeline renvoie une liste de dictionnaires pour les scores
        results = _nli_pipeline(inputs)
        
        # results est généralement sous la forme [[{'label': 'entailment', 'score': 0.98}, ...]]
        # Si on passe un seul input, pipeline peut renvoyer une simple liste [{'label':...}]
        scores_list = results[0] if isinstance(results[0], list) else results

        # Extraction du score de la classe "entailment"
        entailment_score = 0.0
        for s in scores_list:
            if s['label'].lower() == 'entailment' or s['label'] == 'LABEL_1':
                entailment_score = s['score']
                break
                
        return float(entailment_score)

    except Exception as e:
        print(f"Erreur lors de la vérification NLI : {e}", file=sys.stderr)
        return 0.0
