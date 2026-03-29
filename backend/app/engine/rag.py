from typing import List, Dict, Any, Optional
from backend.app.engine.processor import DocumentProcessor
from backend.app.engine.embedding import get_embedding_generator
from backend.app.core.config import settings
from backend.app.mini_vector_db.vector_db import MiniVectorBase

class RAGEngine: 
    def __init__(self):
        self.vector_db = MiniVectorBase(
            storage_path=settings.vector_,
            dimension=settings.VECTOR_DIMENSION
        )
        self.embedding_generator = get_embedding_generator()
        self.document_processor = DocumentProcessor()
    
    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        file_type: str,
        user_id: str,
        document_id: str
    ) -> Dict[str, Any]:
        if file_type == "pdf":
            text = self.document_processor.process_pdf(file_content)
        elif file_type == "docx":
            text = self.document_processor.process_docx(file_content)
        elif file_type == "txt":
            text = self.document_processor.process_txt(file_content)
        elif file_type == "md":
            text = self.document_processor.process_markdown(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")      
        chunks = self.document_processor.chunk_text(
            text,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        if not chunks:
            raise ValueError("No text content extracted from document")
        embeddings = self.embedding_generator.encode_text(chunks)
        metadata_list = [
            {
                "user_id": user_id,
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i,
                "chunk_text": chunk,
                "total_chunks": len(chunks)
            }
            for i, chunk in enumerate(chunks)
        ]
        vector_ids = self.vector_db.add_vectors(embeddings, metadata_list)
        return {
            "text": text,
            "chunks": chunks,
            "vector_ids": vector_ids,
            "chunk_count": len(chunks),
            "metadata": self.document_processor.extract_metadata(
                filename,
                len(file_content),
                file_type,
                text
            )
        }
    
    async def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        query_embedding = self.embedding_generator.encode_query(query)
        filter_metadata = {}
        if user_id:
            filter_metadata["user_id"] = user_id
        results = self.vector_db.search(
            query_embedding,
            top_k=top_k * 2,  
            filter_metadata=filter_metadata if filter_metadata else None
        )
        if document_ids:
            results = [
                r for r in results
                if r["metadata"].get("document_id") in document_ids
            ]
        return results[:top_k]
    
    async def generate_answer(
        self,
        query: str,
        context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not context:
            return {
                "answer": "Xin lỗi, tôi không tìm thấy thông tin liên quan để trả lời câu hỏi của bạn.",
                "sources": [],
                "confidence": 0.0
            }
        context_text = "\n\n".join([
            f"[Nguồn {i+1}]: {item['metadata']['chunk_text']}"
            for i, item in enumerate(context)
        ])
        answer = self._generate_simple_answer(query, context)
        sources = [
            {
                "document_id": item["metadata"]["document_id"],
                "filename": item["metadata"]["filename"],
                "chunk_index": item["metadata"]["chunk_index"],
                "similarity": item["similarity"],
                "text_preview": item["metadata"]["chunk_text"][:200] + "..."
            }
            for item in context
        ]
        return {
            "answer": answer,
            "sources": sources,
            "confidence": float(context[0]["similarity"]) if context else 0.0
        }
    
    def _generate_simple_answer(
        self,
        query: str,
        context: List[Dict[str, Any]]
    ) -> str:
        most_relevant = context[0]["metadata"]["chunk_text"]
        answer = f"""Dựa trên tài liệu, tôi có thể cung cấp thông tin sau:
{most_relevant}
Thông tin này được trích xuất từ tài liệu "{context[0]["metadata"]["filename"]}". """
        if len(context) > 1:
            answer += f"\n\nCó thêm {len(context)-1} nguồn thông tin liên quan khác trong tài liệu."
        return answer
    
    async def summarize_document(
        self,
        document_id: str,
        user_id: str,
        max_length: int = 500
    ) -> str:
        filter_metadata = {
            "document_id": document_id,
            "user_id": user_id
        }
        sample_query = "overview summary content"
        query_embedding = self.embedding_generator.encode_query(sample_query)
        results = self.vector_db.search(
            query_embedding,
            top_k=10,
            filter_metadata=filter_metadata
        )
        if not results:
            raise ValueError("Document not found or access denied")
        all_text = " ".join([
            r["metadata"]["chunk_text"]
            for r in sorted(results, key=lambda x: x["metadata"]["chunk_index"])
        ])
        summary = self._generate_simple_summary(all_text, max_length)
        return summary
    
    def _generate_simple_summary(self, text: str, max_length: int) -> str:
        sentences = text.split('. ')
        summary = ""
        for sentence in sentences:
            if len(summary) + len(sentence) > max_length:
                break
            summary += sentence + ". "
        return summary.strip()
    
    async def delete_document_vectors(self, document_id: str) -> int:
        vector_ids_to_delete = [
            vid for vid, meta in self.vector_db.metadata_store.items()
            if meta.get("document_id") == document_id
        ]
        if vector_ids_to_delete:
            return self.vector_db.delete_vectors(vector_ids_to_delete)
        return 0
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "vector_db_stats": self.vector_db.get_stats(),
            "embedding_model": self.embedding_generator.model_name,
            "embedding_dimension": self.embedding_generator.get_dimension()
        }

_rag_engine: Optional[RAGEngine] = None

def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
