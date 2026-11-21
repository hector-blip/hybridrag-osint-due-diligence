# build_vectorstore.py
import pandas as pd
import faiss
import numpy as np
import pickle
from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

df = pd.read_excel('..\Excel-Data-Abbcari-Battery-materials.xlsx')

# Construire les chunks : un chunk = titre + résumé (Others) par article
def build_chunk(row):
    return (
        f"Title: {row['Title']}\n"
        f"Journal: {row['Journal']} ({row['Year']})\n"
        f"Authors: {row['Authors']}\n"
        f"Affiliations: {row['Affiliations']}\n"
        f"Partners: {row['Partners or funding sources']}\n"
        f"Keywords: {row['Key words']}\n"
        f"Summary: {row['Others']}"
    )

chunks = [build_chunk(row) for _, row in df.iterrows()]
print(f"Nombre de chunks construits : {len(chunks)}")

# Embeddings via OpenAI text-embedding-3-small
def embed_batch(texts, batch_size=100):
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        response = client.embeddings.create(
            input=batch,
            model="text-embedding-3-small"
        )
        embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(embeddings)
        print(f"  Embeddings : {min(i+batch_size, len(texts))}/{len(texts)}")
    return np.array(all_embeddings, dtype='float32')

print("Calcul des embeddings...")
embeddings = embed_batch(chunks)

# Construction de l'index FAISS
dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(embeddings)
print(f"Index FAISS construit : {index.ntotal} vecteurs, dimension {dimension}")

# Sauvegarde
faiss.write_index(index, 'faiss_index.bin')
with open('chunks.pkl', 'wb') as f:
    pickle.dump(chunks, f)
with open('metadata.pkl', 'wb') as f:
    pickle.dump(df.to_dict('records'), f)

print("VectorStore sauvegardé : faiss_index.bin, chunks.pkl, metadata.pkl")