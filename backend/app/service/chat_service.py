from datetime import datetime
import uuid
from pymongo.asynchronous.database import AsyncDatabase
from backend.app.schema.chat import ChatRequest, ChatResponse, ChatMessage

class ChatService:
    def __init__(self, db: AsyncDatabase):
        self.db = db 
        self.collections = self.db.get_collection("chats")

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