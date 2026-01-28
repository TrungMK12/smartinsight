from typing import List, Optional
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from datetime import datetime
from backend.app.engine.rag import Rag
from backend.app.schema.document import DocumentCreate, DocumentInDB, DocumentUpdate

class DocumentService:
    def __init__(self, db: AsyncDatabase):
        self.rag = Rag()
        self.db = db
        self.collection = db.get_collection("documents")

    async def create_document(
        self,
        user_id: str,
        doc_data: DocumentCreate,
        file_content: bytes
    ) -> DocumentInDB:
        doc_dict = doc_data.model_dump()
        doc_dict.update({
            "user_id": user_id,
            "chunks": [],
            "vector_ids": [],
            "metadata": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        results = await self.collection.insert_one(doc_dict)
        document_id = str(results.inserted_id)
        try:
            rag_result = await self.rag_engine.process_document(
                file_content=file_content,
                filename=doc_data.title,
                file_type=doc_data.file_type,
                user_id=user_id,
                document_id=document_id
            )
            await self.collection.update_one(
                {"_id": ObjectId(document_id)},
                {
                    "$set": {
                        "chunks": rag_result["chunks"],
                        "vector_ids": rag_result["vector_ids"],
                        "metadata": rag_result["metadata"]
                    }
                }
            )
            doc = await self.collection.find_one({"_id": ObjectId(document_id)})
            doc["_id"] = str(doc["_id"])
            return DocumentInDB(**doc)
        except Exception as e:
            await self.collection.delete_one({"_id": ObjectId(document_id)})
            raise ValueError(f"Failed to process document: {str(e)}")
        
    async def get_document(self, document_id: str, user_id: str) -> Optional[DocumentInDB]:
        if not ObjectId.is_valid(document_id):
            return None
        doc = await self.collection.find_one({
            "_id": ObjectId(document_id),
            "user_id": user_id
        })
        if doc:
            doc["_id"] = str(doc["_id"])
            return DocumentInDB(**doc)
        return None
    
    async def list_user_documents(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[DocumentInDB]:
        cursor = self.collection.find({"user_id": user_id})
        cursor = cursor.sort("created_at", -1).skip(skip).limit(limit)
        documents = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            documents.append(DocumentInDB(**doc))
        return documents
    
    async def update_document(
        self,
        document_id: str,
        user_id: str,
        update_data: DocumentUpdate
    ) -> Optional[DocumentInDB]:
        if not ObjectId.is_valid(document_id):
            return None
        update_dict = update_data.model_dump(exclude_unset=True)
        update_dict["updated_at"] = datetime.utcnow()
        result = await self.collection.find_one_and_update(
            {"_id": ObjectId(document_id), "user_id": user_id},
            {"$set": update_dict},
            return_document=ReturnDocument.AFTER
        )
        if result:
            result["_id"] = str(result["_id"])
            return DocumentInDB(**result)
        return None

    async def delete_document(self, document_id: str, user_id: str) -> bool:
        if not ObjectId.is_valid(document_id):
            return False
        doc = await self.get_document(document_id, user_id)
        if not doc:
            return False
        await self.rag_engine.delete_document_vectors(document_id)
        result = await self.collection.delete_one({
            "_id": ObjectId(document_id),
            "user_id": user_id
        })
        return result.deleted_count > 0
    
    async def count_user_documents(self, user_id: str) -> int:
        return await self.collection.count_documents({"user_id": user_id})

