from __future__ import annotations

import logging
from typing import Any

try:
    import chromadb
    from chromadb.api.models.Collection import Collection
except Exception:  # pragma: no cover - optional dependency in some environments
    chromadb = None
    Collection = Any

from config import ROOT_DIR, SETTINGS, ensure_data_dirs


logger = logging.getLogger(__name__)


class ChromaIssueStore:
    def __init__(self, collection_name: str = "issue_reference") -> None:
        self.client = None
        self.collection = None

        if chromadb is None:
            logger.warning("chromadb unavailable; vector retrieval disabled for this runtime")
            return

        ensure_data_dirs()
        persist_dir = (ROOT_DIR / SETTINGS.chroma_persist_dir).resolve().as_posix()
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection: Collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Issue reference snippets for retrieval"},
        )

    def upsert_documents(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if self.collection is None:
            return
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def query(self, text: str, limit: int = 8) -> list[dict[str, Any]]:
        if self.collection is None:
            return []

        result = self.collection.query(
            query_texts=[text],
            n_results=limit,
        )

        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        rows: list[dict[str, Any]] = []
        for idx, document in enumerate(docs):
            rows.append(
                {
                    "document": document,
                    "metadata": metas[idx] if idx < len(metas) else {},
                    "distance": distances[idx] if idx < len(distances) else None,
                }
            )
        return rows
