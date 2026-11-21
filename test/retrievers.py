# retrievers.py
import faiss
import pickle
import numpy as np
from dotenv import load_dotenv
import os
from openai import OpenAI
from neo4j import GraphDatabase

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", os.getenv("NEO4J_PASSWORD")))

# Charger FAISS
index  = faiss.read_index('faiss_index.bin')
with open('chunks.pkl', 'rb') as f:
    chunks = pickle.load(f)

def embed_query(query):
    response = client.embeddings.create(
        input=[query],
        model="text-embedding-3-small"
    )
    return np.array([response.data[0].embedding], dtype='float32')

def generate_answer(context, question):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Tu es un expert en analyse OSINT de publications scientifiques "
                "sur les batteries. Réponds uniquement en te basant sur le contexte fourni. "
                "Si l'information n'est pas dans le contexte, dis-le explicitement."
            )},
            {"role": "user", "content": f"Contexte :\n{context}\n\nQuestion : {question}"}
        ],
        temperature=0
    )
    return response.choices[0].message.content

# ── C1 : VectorRAG seul ──────────────────────────────────────────
def retrieval_vector(query, top_k=5):
    q_vec = embed_query(query)
    distances, indices = index.search(q_vec, top_k)
    return [chunks[i] for i in indices[0] if i < len(chunks)]

def c1_vector_rag(question):
    contexts = retrieval_vector(question)
    context  = "\n\n---\n\n".join(contexts)
    answer   = generate_answer(context, question)
    return {"answer": answer, "contexts": contexts}

# ── C2 : GraphRAG seul ───────────────────────────────────────────
def retrieval_graph(query):
    # Extraire entités clés via LLM
    extraction = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": (
            f"Extrais les entités principales (chercheurs, institutions, mots-clés) "
            f"de cette question pour une recherche dans un graphe de connaissances. "
            f"Réponds avec une liste séparée par des virgules, rien d'autre.\n\nQuestion : {query}"
        )}],
        temperature=0
    )
    entities = [e.strip() for e in extraction.choices[0].message.content.split(',')]

    contexts = []
    with driver.session() as session:
        for entity in entities[:3]:  # Limiter à 3 entités
            # Recherche dans le graphe
            result = session.run("""
                MATCH (n)
                WHERE toLower(n.name) CONTAINS toLower($entity)
                WITH n LIMIT 1
                MATCH (n)-[r]-(neighbor)
                RETURN n.name AS source,
                       type(r) AS relation,
                       neighbor.name AS target
                LIMIT 20
            """, entity=entity)
            
            triplets = [f"{row['source']} --[{row['relation']}]--> {row['target']}"
                       for row in result]
            if triplets:
                contexts.append(f"Entité '{entity}' :\n" + "\n".join(triplets))

    return contexts

def c2_graph_rag(question):
    contexts = retrieval_graph(question)
    context  = "\n\n---\n\n".join(contexts) if contexts else "Aucune entité trouvée dans le graphe."
    answer   = generate_answer(context, question)
    return {"answer": answer, "contexts": contexts}

# ── C3 : HybridRAG sans HITL ────────────────────────────────────
def c3_hybrid_no_hitl(question):
    vector_contexts = retrieval_vector(question, top_k=3)
    graph_contexts  = retrieval_graph(question)
    
    all_contexts = vector_contexts + graph_contexts
    context = "\n\n---\n\n".join(all_contexts)
    answer  = generate_answer(context, question)
    return {"answer": answer, "contexts": all_contexts}

# ── C4 : HybridRAG avec HITL ────────────────────────────────────
# Note : pour C4, le graphe utilisé est celui dont les triplets
# ont été validés par l'expert via ton interface Streamlit.
# La fonction est identique à C3 — la différence est dans le graphe Neo4j chargé.
# Lance C4 APRÈS avoir exécuté ta validation HITL dans Streamlit.
def c4_hybrid_hitl(question):
    return c3_hybrid_no_hitl(question)  # Même logique, graphe validé différent