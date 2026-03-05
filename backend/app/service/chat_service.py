from datetime import datetime
from typing import List, Optional
import uuid
from pymongo.asynchronous.database import AsyncDatabase
from backend.app.schema.chat import ChatHistoryInDB, ChatRequest, ChatResponse, ChatMessage

class ChatService:
    def __init__(self, db: AsyncDatabase):
        self.db = db 
        self.collections = self.db.get_collection("chats")
        self.rag_engine = get_rag_engine()

    async def process_query(
        self,
        user_id: str,
        chat_request: ChatRequest
    ) -> ChatResponse:
        session_id = chat_request.session_id or str(uuid.uuid4())
        context = await self.rag_engine.retrieve_context(
            query=chat_request.query,
            top_k=chat_request.max_docs,
            user_id=user_id,
            document_ids=chat_request.document_ids
        )
        result = await self.rag_engine.generate_answer(
            query=chat_request.query,
            context=context
        )
        await self._save_chat_message(
            user_id=user_id,
            session_id=session_id,
            messages=[
                ChatMessage(role="user", content=chat_request.query),
                ChatMessage(role="assistant", content=result["answer"])
            ]
        )
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            session_id=session_id,
            timestamp=datetime.utcnow()
        )
    
    async def summarize_document(
        self,
        user_id: str,
        document_id: str,
        max_length: int = 500
    ) -> str:
        summary = await self.rag_engine.summarize_document(
            document_id=document_id,
            user_id=user_id,
            max_length=max_length
        )
        return summary

    async def _save_chat_message(
        self,
        user_id: str,
        session_id: str,
        messages: List[ChatMessage]
    ):
        existing_session = await self.collection.find_one({
            "user_id": user_id,
            "session_id": session_id
        })
        if existing_session:
            await self.collection.update_one(
                {"_id": existing_session["_id"]},
                {
                    "$push": {
                        "messages": {"$each": [m.model_dump() for m in messages]}
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        else:
            await self.collection.insert_one({
                "user_id": user_id,
                "session_id": session_id,
                "messages": [m.model_dump() for m in messages],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
    
    async def get_chat_history(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[ChatHistoryInDB]:
        query = {"user_id": user_id}
        if session_id:
            query["session_id"] = session_id
        cursor = self.collection.find(query)
        cursor = cursor.sort("updated_at", -1).limit(limit)
        history = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            history.append(ChatHistoryInDB(**doc))
        return history
    
    async def delete_chat_session(self, user_id: str, session_id: str) -> bool:
        result = await self.collection.delete_one({
            "user_id": user_id,
            "session_id": session_id
        })
        return result.deleted_count > 0