import sys
import os
import json
import asyncio
from typing import List

# Force UTF-8 sur Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from backend.models import Triplet

BATCH_SIZE = 15          # articles par appel LLM
MAX_CONCURRENT = 5       # appels LLM en parallèle max (évite le rate-limit)

class LLMExtraction(BaseModel):
    triplets: List[Triplet] = Field(..., description="List of knowledge graph triplets extracted from the articles")


def _build_chain():
    """Construit la chaîne LangChain (prompt + structured LLM)."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(LLMExtraction)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an expert scientific due diligence system.\n"
         "Your objective is to read batches of academic articles and identify strictly the AUTHORS who meet the user's specific need.\n"
         "Target Need:\n{need_description}\n\n"
         "Strict Extraction Rules imposed by the user:\n{rules_str}\n\n"
         "Instructions:\n"
         "1. Read the provided JSON list of articles. Each article may have: Title, Authors, Affiliations, Abstract, Journal, Partners or funding sources, Key words, Others, etc.\n"
         "2. For authors whose work matches the target need AND respects the extraction rules, output Triplets.\n"
         "3. Required Triplets per valid author:\n"
         "   - (Author) -[AFFILIÉ_À]-> (Institution)\n"
         "   - (Author) -[A_POUR_EXPERTISE]-> (Specific Concept matching the need)\n"
         "4. Highly Recommended Triplets if the relevant data exists in the fields (like 'Journal', 'Partners or funding sources', or 'Key words'):\n"
         "   - (Author) -[PARTENAIRE_DE]-> (Partner/Funding Source) (type: Partner)\n"
         "   - (Author) -[TRAVAILLE_SUR]-> (Keyword) (type: Keyword)\n"
         "   - (Author) -[PUBLIÉ_DANS]-> (Journal) (type: Journal)\n"
         "5. Include a direct justification quote from the abstract, the keywords, or the partners/others metadata for the relation.\n"
         "6. Add confidence scores and the article Source DOI/URL."),
        ("human", "Articles to analyze:\n{text}")
    ])

    return prompt | structured_llm


async def _process_batch(
    batch_index: int,
    batch: list,
    need_description: str,
    rules_str: str,
    semaphore: asyncio.Semaphore
) -> List[Triplet]:
    """Traite un lot d'articles en asynchrone avec contrôle de concurrence."""
    async with semaphore:
        chain = _build_chain()
        batch_json = json.dumps(batch, indent=2, ensure_ascii=True)
        try:
            print(f"[llm_parser] Lot {batch_index + 1}: envoi de {len(batch)} articles au LLM...")
            result = await chain.ainvoke({
                "need_description": need_description,
                "rules_str": rules_str,
                "text": batch_json
            })
            print(f"[llm_parser] Lot {batch_index + 1}: {len(result.triplets)} triplets extraits.")
            return result.triplets
        except Exception as e:
            print(f"[llm_parser] Lot {batch_index + 1}: ERREUR → {e}")
            return []


async def extract_knowledge_async(
    articles: list,
    need_description: str,
    extraction_rules: List[str]
) -> List[Triplet]:
    """
    Version asynchrone avec batching parallèle.
    Divise les articles en lots de BATCH_SIZE et les traite en parallèle
    (jusqu'à MAX_CONCURRENT appels simultanés).
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY non défini. Utilisation de valeurs mock.")
        return [
            Triplet(
                subject="Dr. Alice Smith", subject_type="Author",
                relation="AFFILIÉ_À", object="MIT Battery Lab", object_type="Institution",
                justification="Listed as affiliation in the paper.",
                confidence=0.99, source_url="mock_DOI_1"
            ),
            Triplet(
                subject="Dr. Alice Smith", subject_type="Author",
                relation="A_POUR_EXPERTISE", object="Lithium-ion solid-state synthesis", object_type="Skill",
                justification="We developed a breakthrough synthesis method...",
                confidence=0.95, source_url="mock_DOI_1"
            )
        ]

    rules_str = "\n".join([f"- {r}" for r in extraction_rules])

    # Découpage en lots
    batches = [articles[i:i + BATCH_SIZE] for i in range(0, len(articles), BATCH_SIZE)]
    total_batches = len(batches)
    print(f"[llm_parser] {len(articles)} articles → {total_batches} lots de {BATCH_SIZE} "
          f"(max {MAX_CONCURRENT} en parallèle)")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    tasks = [
        _process_batch(i, batch, need_description, rules_str, semaphore)
        for i, batch in enumerate(batches)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_triplets: List[Triplet] = []
    for r in results:
        if isinstance(r, list):
            all_triplets.extend(r)
        elif isinstance(r, Exception):
            print(f"[llm_parser] Exception lors d'un lot : {r}")

    print(f"[llm_parser] Extraction complète : {len(all_triplets)} triplets au total.")
    return all_triplets


# ─── Compatibilité synchrone (conservée pour rétrocompatibilité) ──────────────

def extract_knowledge(articles_json: str, need_description: str, extraction_rules: List[str]) -> List[Triplet]:
    """
    Version synchrone legacy — accepte un JSON string.
    Utilisée uniquement si appelée hors contexte async.
    """
    articles = json.loads(articles_json)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Déjà dans une boucle async → créer une tâche dans un thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, extract_knowledge_async(articles, need_description, extraction_rules))
                return future.result()
        else:
            return loop.run_until_complete(extract_knowledge_async(articles, need_description, extraction_rules))
    except RuntimeError:
        return asyncio.run(extract_knowledge_async(articles, need_description, extraction_rules))
