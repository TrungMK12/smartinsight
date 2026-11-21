"""Vector store tối giản, chạy in-process, persist ra đĩa.

Định dạng lưu trữ (trong ``storage_path``):
    vectors.npy  - ma trận float32 shape (N, dimension), mỗi hàng đã chuẩn hoá L2
    meta.json    - {"dimension": int, "ids": [...], "metadata": {id: {...}}}

Ghi chú:
    - Mọi thao tác đều được bảo vệ bởi ``threading.RLock`` vì FastAPI xử lý
      request trên threadpool.
    - Store chạy trong 1 process => chỉ dùng ``uvicorn --workers 1``.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

VECTORS_FILE = "vectors.npy"
METADATA_FILE = "meta.json"


class MiniVectorBase:
    def __init__(
        self,
        storage_path: Optional[str | os.PathLike] = None,
        dimension: Optional[int] = None,
        autosave: bool = True,
    ) -> None:
        self.storage_path = Path(storage_path) if storage_path else None
        self.dimension = dimension
        self.autosave = autosave
        self._vectors: np.ndarray = np.empty(
            (0, dimension or 0), dtype=np.float32
        )
        self._ids: List[str] = []
        self.metadata_store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self.load()

    # ------------------------------------------------------------------ #
    # Read-only helpers
    # ------------------------------------------------------------------ #
    @property
    def vectors(self) -> np.ndarray:
        return self._vectors

    @property
    def ids(self) -> List[str]:
        return list(self._ids)

    def __len__(self) -> int:
        return len(self._ids)

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #
    def add_vectors(
        self,
        embeddings: np.ndarray,
        metadata_list: List[Dict[str, Any]],
    ) -> List[str]:
        embeddings = np.asarray(embeddings, dtype=np.float32)
        if embeddings.size == 0:
            return []
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        if embeddings.ndim != 2:
            raise ValueError("embeddings phải là mảng 2 chiều (N, dimension)")
        if len(embeddings) != len(metadata_list):
            raise ValueError(
                "Số lượng embeddings và metadata không khớp: "
                f"{len(embeddings)} != {len(metadata_list)}"
            )

        incoming_dim = int(embeddings.shape[1])
        with self._lock:
            if self.dimension is None:
                self.dimension = incoming_dim
            elif incoming_dim != self.dimension:
                raise ValueError(
                    "Sai dimension embedding: "
                    f"store={self.dimension}, nhận={incoming_dim}. "
                    "Kiểm tra VECTOR_MODELNAME và VECTOR_DIMENSION."
                )

            embeddings = self._normalize(embeddings)
            new_ids = [str(uuid.uuid4()) for _ in range(len(embeddings))]

            self._vectors = np.vstack([self._vectors, embeddings])
            self._ids.extend(new_ids)
            for vector_id, metadata in zip(new_ids, metadata_list):
                self.metadata_store[vector_id] = dict(metadata)

            self._maybe_save()
            return new_ids

    def delete_vectors(self, vector_ids: List[str]) -> int:
        with self._lock:
            to_delete = {vid for vid in vector_ids if vid in self.metadata_store}
            if not to_delete:
                return 0

            keep_mask = np.array(
                [vid not in to_delete for vid in self._ids], dtype=bool
            )
            self._vectors = self._vectors[keep_mask]
            self._ids = [
                vid for vid in self._ids if vid not in to_delete
            ]
            for vid in to_delete:
                self.metadata_store.pop(vid, None)

            self._maybe_save()
            return len(to_delete)

    def delete_where(self, filter_metadata: Dict[str, Any]) -> int:
        """Xoá mọi vector có metadata khớp toàn bộ ``filter_metadata``."""
        with self._lock:
            matching = [
                vid
                for vid, metadata in self.metadata_store.items()
                if self._matches(metadata, filter_metadata)
            ]
            return self.delete_vectors(matching)

    def clear(self) -> None:
        with self._lock:
            self._vectors = np.empty(
                (0, self.dimension or 0), dtype=np.float32
            )
            self._ids = []
            self.metadata_store = {}
            self._maybe_save()

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            if not self._ids:
                return []

            query = np.asarray(query_vector, dtype=np.float32).ravel()
            if self.dimension and query.shape[0] != self.dimension:
                raise ValueError(
                    "Sai dimension query: "
                    f"store={self.dimension}, nhận={query.shape[0]}"
                )
            query = self._normalize(query.reshape(1, -1))[0]

            candidate_indices = [
                idx
                for idx, vid in enumerate(self._ids)
                if filter_metadata is None
                or self._matches(self.metadata_store[vid], filter_metadata)
            ]
            if not candidate_indices:
                return []

            matrix = self._vectors[candidate_indices]
            similarities = matrix @ query

            order = np.argsort(-similarities, kind="stable")[: max(top_k, 1)]
            results: List[Dict[str, Any]] = []
            for pos in order:
                vector_id = self._ids[candidate_indices[int(pos)]]
                results.append(
                    {
                        "id": vector_id,
                        "similarity": float(similarities[int(pos)]),
                        "metadata": self.metadata_store[vector_id],
                    }
                )
            return results

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            per_user: Dict[str, int] = {}
            for metadata in self.metadata_store.values():
                user_id = metadata.get("user_id")
                if user_id:
                    per_user[user_id] = per_user.get(user_id, 0) + 1
            return {
                "total_vectors": len(self._ids),
                "dimension": self.dimension,
                "storage_path": str(self.storage_path) if self.storage_path else None,
                "vectors_per_user": per_user,
            }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def save(self, file_path: Optional[str | os.PathLike] = None) -> None:
        target = Path(file_path) if file_path else self.storage_path
        if target is None:
            return
        target.mkdir(parents=True, exist_ok=True)

        with self._lock:
            vectors_tmp = target / ".vectors.tmp.npy"
            metadata_tmp = target / ".meta.tmp.json"

            np.save(vectors_tmp, self._vectors)
            payload = {
                "dimension": self.dimension,
                "ids": self._ids,
                "metadata": self.metadata_store,
            }
            with open(metadata_tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)

            os.replace(vectors_tmp, target / VECTORS_FILE)
            os.replace(metadata_tmp, target / METADATA_FILE)

    def load(self, file_path: Optional[str | os.PathLike] = None) -> bool:
        target = Path(file_path) if file_path else self.storage_path
        if target is None:
            return False

        vectors_file = target / VECTORS_FILE
        metadata_file = target / METADATA_FILE
        if not vectors_file.exists() or not metadata_file.exists():
            return False

        with self._lock:
            vectors = np.load(vectors_file, allow_pickle=False)
            with open(metadata_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

            ids = payload.get("ids", [])
            metadata_store = payload.get("metadata", {})
            if len(ids) != len(vectors):
                raise ValueError(
                    "Vector store bị hỏng: số id và số vector không khớp "
                    f"({len(ids)} != {len(vectors)})"
                )

            self._vectors = np.asarray(vectors, dtype=np.float32)
            self._ids = list(ids)
            self.metadata_store = dict(metadata_store)
            self.dimension = payload.get("dimension") or (
                int(self._vectors.shape[1]) if self._vectors.ndim == 2 else None
            )
            return True

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-10)

    @staticmethod
    def _matches(
        metadata: Dict[str, Any], filter_metadata: Dict[str, Any]
    ) -> bool:
        return all(
            metadata.get(key) == value
            for key, value in filter_metadata.items()
        )

    def _maybe_save(self) -> None:
        if self.autosave and self.storage_path:
            self.save()
