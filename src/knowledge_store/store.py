import os
import json
from typing import List, Dict, Optional, Any
from src.schemas import Chunk, ChunkDoc, EvalResult, TestResult

class KnowledgeStore:
    def __init__(self, storage_dir: str = ".knowledge_store"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.docs_file = os.path.join(self.storage_dir, "chunk_docs.json")
        self.flagged_file = os.path.join(self.storage_dir, "flagged_items.json")
        self.evals_file = os.path.join(self.storage_dir, "eval_results.json")   # NEW

        self.docs: Dict[str, dict] = self._load_json(self.docs_file)
        self.flagged_items: List[dict] = self._load_json(self.flagged_file, default=[])
        self.evals: Dict[str, dict] = self._load_json(self.evals_file)          # NEW

        self.vector_documents: List[dict] = []

    def _load_json(self, path: str, default=None):
        if default is None:
            default = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return default
        return default

    def _save_json(self, data: Any, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def save_doc(self, doc: ChunkDoc):
        self.docs[doc.chunk_id] = doc.model_dump()
        self._save_json(self.docs, self.docs_file)
        self.vector_documents.append({
            "chunk_id": doc.chunk_id,
            "text": f"{doc.summary}\n{doc.business_logic}",
            "metadata": doc.model_dump()
        })

    def get_doc(self, chunk_id: str) -> Optional[ChunkDoc]:
        data = self.docs.get(chunk_id)
        if data:
            return ChunkDoc.model_validate(data)
        return None

    def save_eval(self, eval_result: EvalResult) -> None:   # NEW
        self.evals[eval_result.chunk_id] = eval_result.model_dump()
        self._save_json(self.evals, self.evals_file)

    def get_all_evals(self) -> Dict[str, dict]:              # NEW
        return self.evals

    def flag_for_review(self, chunk_id: str, score: float, issues: List[str], reason: str = ""):
        item = {
            "chunk_id": chunk_id,
            "overall_score": score,
            "issues": issues,
            "reason": reason
        }
        self.flagged_items.append(item)
        self._save_json(self.flagged_items, self.flagged_file)

    def get_flagged_items(self) -> List[dict]:
        return self._load_json(self.flagged_file, default=[])

    def similarity_search(self, query: str, k: int = 3) -> List[ChunkDoc]:
        """Simple keyword/substring vector similarity fallback for testing."""
        results = []
        words = query.lower().split()
        for v in self.vector_documents:
            text = v["text"].lower()
            if any(w in text for w in words):
                results.append(ChunkDoc.model_validate(v["metadata"]))
                if len(results) >= k:
                    break
        if not results:
            for d in list(self.docs.values())[:k]:
                results.append(ChunkDoc.model_validate(d))
        return results