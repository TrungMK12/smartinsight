import asyncio
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.config import settings
from backend.app.engine.rag import get_rag_engine
from backend.app.schema.document import DocumentCreate, DocumentInDB, DocumentUpdate


class DuplicateDocumentError(ValueError):
    """Người dùng đã upload đúng file này trước đó."""


class DocumentService:
    def __init__(self, db: AsyncDatabase):
        self.db = db
        self.collection = db.get_collection("documents")
        self.rag_engine = get_rag_engine()

    # ------------------------------------------------------------------ #
    # Create / process
    # ------------------------------------------------------------------ #
    async def create_document(
        self,
        user_id: str,
        doc_data: DocumentCreate,
        file_content: bytes,
    ) -> DocumentInDB:
        checksum = hashlib.sha256(file_content).hexdigest()
        existing = await self.collection.find_one(
            {"user_id": user_id, "checksum": checksum}
        )
        if existing:
            raise DuplicateDocumentError(
                f"Tài liệu đã tồn tại (id={existing['_id']})"
            )

        file_path = self._build_file_path(user_id, doc_data.file_type)
        await asyncio.to_thread(self._write_file, file_path, file_content)

        now = datetime.utcnow()
        doc_dict = doc_data.model_dump()
        doc_dict.update(
            {
                "user_id": user_id,
                "chunks": [],
                "vector_ids": [],
                "metadata": {},
                "file_path": file_path,
                "checksum": checksum,
                "status": "pending",
                "chunk_count": 0,
                "error_message": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        result = await self.collection.insert_one(doc_dict)
        doc_dict["_id"] = str(result.inserted_id)
        return DocumentInDB(**doc_dict)

    async def process_document(self, document_id: str, user_id: str) -> None:
        """Chạy RAG cho tài liệu (dùng làm background task)."""
        doc = await self._get_raw(document_id, user_id)
        if not doc:
            return

        await self._set_status(doc["_id"], "processing")
        try:
            file_path = doc.get("file_path")
            if not file_path:
                raise ValueError("Không tìm thấy đường dẫn file gốc")

            file_content = await asyncio.to_thread(Path(file_path).read_bytes)
            rag_result = await self.rag_engine.process_document(
                file_content=file_content,
                filename=doc.get("title") or "document",
                file_type=doc["file_type"],
                user_id=user_id,
                document_id=document_id,
            )
            await self.collection.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "chunks": rag_result["chunks"],
                        "vector_ids": rag_result["vector_ids"],
                        "metadata": rag_result["metadata"],
                        "chunk_count": rag_result["chunk_count"],
                        "status": "ready",
                        "error_message": None,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
        except Exception as e:
            # Không để lại vector rác khi xử lý thất bại
            await self.rag_engine.delete_document_vectors(document_id)
            await self.collection.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": str(e)[:500],
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

    async def prepare_reindex(
        self, document_id: str, user_id: str
    ) -> Optional[DocumentInDB]:
        doc = await self.get_document(document_id, user_id)
        if not doc:
            return None
        if not doc.file_path or not await asyncio.to_thread(
            Path(doc.file_path).exists
        ):
            raise ValueError("Không tìm thấy file gốc để xử lý lại")

        await self.rag_engine.delete_document_vectors(document_id)
        await self.collection.update_one(
            {"_id": ObjectId(document_id)},
            {
                "$set": {
                    "status": "pending",
                    "chunks": [],
                    "vector_ids": [],
                    "chunk_count": 0,
                    "error_message": None,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return doc

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    async def get_document(
        self, document_id: str, user_id: str
    ) -> Optional[DocumentInDB]:
        doc = await self._get_raw(document_id, user_id)
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        return DocumentInDB(**doc)

    async def list_user_documents(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> List[DocumentInDB]:
        cursor = self.collection.find({"user_id": user_id})
        cursor = cursor.sort("created_at", -1).skip(skip).limit(limit)
        documents = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            documents.append(DocumentInDB(**doc))
        return documents

    async def count_user_documents(self, user_id: str) -> int:
        return await self.collection.count_documents({"user_id": user_id})

    # ------------------------------------------------------------------ #
    # Update / delete
    # ------------------------------------------------------------------ #
    async def update_document(
        self,
        document_id: str,
        user_id: str,
        update_data: DocumentUpdate,
    ) -> Optional[DocumentInDB]:
        if not ObjectId.is_valid(document_id):
            return None
        update_dict = update_data.model_dump(exclude_unset=True)
        update_dict["updated_at"] = datetime.utcnow()
        result = await self.collection.find_one_and_update(
            {"_id": ObjectId(document_id), "user_id": user_id},
            {"$set": update_dict},
            return_document=ReturnDocument.AFTER,
        )
        if result:
            result["_id"] = str(result["_id"])
            return DocumentInDB(**result)
        return None

    async def delete_document(self, document_id: str, user_id: str) -> bool:
        doc = await self.get_document(document_id, user_id)
        if not doc:
            return False

        await self.rag_engine.delete_document_vectors(document_id)
        if doc.file_path:
            await asyncio.to_thread(self._remove_file, doc.file_path)
        result = await self.collection.delete_one(
            {"_id": ObjectId(document_id), "user_id": user_id}
        )
        return result.deleted_count > 0

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    async def _get_raw(self, document_id: str, user_id: str) -> Optional[dict]:
        if not ObjectId.is_valid(document_id):
            return None
        return await self.collection.find_one(
            {"_id": ObjectId(document_id), "user_id": user_id}
        )

    async def _set_status(self, object_id: ObjectId, status: str) -> None:
        await self.collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": status,
                    "error_message": None,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    @staticmethod
    def _build_file_path(user_id: str, file_type: str) -> str:
        return str(
            Path(settings.upload_dir) / user_id / f"{uuid.uuid4().hex}.{file_type}"
        )

    @staticmethod
    def _write_file(file_path: str, content: bytes) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    @staticmethod
    def _remove_file(file_path: str) -> None:
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError:
            pass
