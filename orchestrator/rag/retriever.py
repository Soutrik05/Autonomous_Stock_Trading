# =============================================================================
# orchestrator/rag/retriever.py
#
# Loads the FAISS index from disk and retrieves relevant context chunks
# for a given stock before the LLM reasoning call.
#
# Four lanes queried separately so no type crowds out another:
#   price_technical  — price history + RSI/MACD/EMA/BB/OBV
#   fundamental      — PE, ROE, debt, margins, growth
#   news             — headlines and sentiment
#   sector           — macro sector performance
# =============================================================================

import os
import json
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

DB_PATH = "rag_db"


class Retriever:

    def __init__(self):
        cfg_path = os.path.join(DB_PATH, "config.json")
        if not os.path.exists(cfg_path):
            raise FileNotFoundError(
                f"RAG database not found at {DB_PATH}/. "
                "Run main.py once to build it automatically."
            )
        with open(cfg_path) as f:
            cfg = json.load(f)

        self.model  = SentenceTransformer(cfg["model"])
        self.index  = faiss.read_index(os.path.join(DB_PATH, "faiss.index"))
        with open(os.path.join(DB_PATH, "metadata.pkl"), "rb") as f:
            self.chunks = pickle.load(f)

        print(f"✅  RAG loaded  {cfg['total']} vectors  "
              f"(built {cfg['created_at'][:10]})")

    def _query(self, query: str, top_k: int = 3,
               filter_type: str = None) -> list[str]:
        emb = self.model.encode([query]).astype("float32")
        faiss.normalize_L2(emb)
        k        = min(top_k * 6 if filter_type else top_k, self.index.ntotal)
        _, idxs  = self.index.search(emb, k)
        results  = []
        for i in idxs[0]:
            if i >= len(self.chunks):
                continue
            c = self.chunks[i]
            if filter_type and c.get("type") != filter_type:
                continue
            results.append(c["text"])
            if len(results) >= top_k:
                break
        return results

    def get_context_for_stock(self, symbol: str, sector: str) -> str:
        tech_ctx   = self._query(f"{symbol} RSI MACD EMA momentum technical", 2, "price_technical")
        fund_ctx   = self._query(f"{symbol} PE ROE debt margins fundamentals",  2, "fundamental")
        news_ctx   = self._query(f"{symbol} {sector} news sentiment",           2, "news")
        sector_ctx = self._query(f"{sector} sector performance outlook",         1, "sector")

        def _fmt(label, items):
            return f"{label}:\n" + ("\n---\n".join(items) if items else "No data.")

        return "\n\n".join([
            _fmt("PRICE + TECHNICAL CONTEXT (RAG)", tech_ctx),
            _fmt("FUNDAMENTAL CONTEXT (RAG)",        fund_ctx),
            _fmt("NEWS CONTEXT (RAG)",               news_ctx),
            _fmt("SECTOR CONTEXT (RAG)",             sector_ctx),
        ])