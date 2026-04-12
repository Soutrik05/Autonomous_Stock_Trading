# =============================================================================
# orchestrator/rag/embedder.py
#
# Embeds all data chunks into a local FAISS index.
# Uses sentence-transformers all-MiniLM-L6-v2 (no API key, ~90 MB download).
# Saves faiss.index + metadata.pkl + config.json to rag_db/.
# =============================================================================

import os
import json
import sys
import pickle
from datetime import datetime

import faiss
from sentence_transformers import SentenceTransformer


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orchestrator.rag.data_fetcher import DataFetcher

DB_PATH    = "rag_db"
MODEL_NAME = "all-MiniLM-L6-v2"


class Embedder:

    def __init__(self):
        os.makedirs(DB_PATH, exist_ok=True)
        print(f"  Loading embedding model ({MODEL_NAME})...")
        self.model = SentenceTransformer(MODEL_NAME)

    def build_all(self):
        chunks = DataFetcher().fetch_all()
        if not chunks:
            raise RuntimeError("No chunks returned — check network/API access.")

        texts      = [c["text"] for c in chunks]
        print(f"\n  Embedding {len(texts)} chunks (this takes 2-4 min on CPU)...")
        embeddings = self.model.encode(
            texts, batch_size=64, show_progress_bar=True, convert_to_numpy=True
        ).astype("float32")

        faiss.normalize_L2(embeddings)

        dim   = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        faiss.write_index(index, f"{DB_PATH}/faiss.index")
        with open(f"{DB_PATH}/metadata.pkl", "wb") as f:
            pickle.dump(chunks, f)

        config = {
            "model":      MODEL_NAME,
            "dimension":  dim,
            "total":      index.ntotal,
            "created_at": datetime.now().isoformat(),
            "by_type":    {t: sum(1 for c in chunks if c["type"]==t)
                           for t in {c["type"] for c in chunks}},
        }
        with open(f"{DB_PATH}/config.json", "w") as f:
            json.dump(config, f, indent=2)

        print(f"\n  FAISS index: {index.ntotal} vectors  dim={dim}")
        print(f"    Saved to ./{DB_PATH}/")
        print(f"    Breakdown: {config['by_type']}")
        return index.ntotal


if __name__ == "__main__":
    
    embedder = Embedder() 
    embedder.build_all()