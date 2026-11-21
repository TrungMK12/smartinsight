import asyncio
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.engine.embedding import get_embedding_generator
from backend.app.engine.processor import DocumentProcessor
from backend.app.mini_vector_db.vector_db import MiniVectorBase


class RAGEngine:
    def __init__(self) -> None:
        self.vector_db = MiniVectorBase(
            storage_path=settings.vector_db_path,
            dimension=settings.vector_dimension,
        )
        self.embedding_generator = get_embedding_generator()
        self.document_processor = DocumentProcessor()

    # ------------------------------------------------------------------ #
    # Indexing
    # ------------------------------------------------------------------ #
    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        file_type: str,
        user_id: str,
        document_id: str,
    ) -> Dict[str, Any]:
        text = await asyncio.to_thread(
            self._extract_text, file_content, file_type
        )
        chunks = await asyncio.to_thread(
            self.document_processor.chunk_text,
            text,
            settings.chunk_size,
            settings.chunk_overlap,
        )
        if not chunks:
            raise ValueError("No text content extracted from document")

        embeddings = await asyncio.to_thread(
            self.embedding_generator.encode_text, chunks
        )
        metadata_list = [
            {
                "user_id": user_id,
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i,
                "chunk_text": chunk,
                "total_chunks": len(chunks),
            }
            for i, chunk in enumerate(chunks)
        ]
        vector_ids = await asyncio.to_thread(
            self.vector_db.add_vectors, embeddings, metadata_list
        )
        return {
            "text": text,
            "chunks": chunks,
            "vector_ids": vector_ids,
            "chunk_count": len(chunks),
            "metadata": self.document_processor.extract_metadata(
                filename, len(file_content), file_type, text
            ),
        }

    def _extract_text(self, file_content: bytes, file_type: str) -> str:
        processors = {
            "pdf": self.document_processor.process_pdf,
            "docx": self.document_processor.process_docx,
            "txt": self.document_processor.process_txt,
            "md": self.document_processor.process_markdown,
        }
        processor = processors.get(file_type)
        if processor is None:
            raise ValueError(f"Unsupported file type: {file_type}")
        return processor(file_content)

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #
    async def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        query_embedding = await asyncio.to_thread(
            self.embedding_generator.encode_query, query
        )
        filter_metadata: Dict[str, Any] = {}
        if user_id:
            filter_metadata["user_id"] = user_id

        results = await asyncio.to_thread(
            self.vector_db.search,
            query_embedding,
            top_k * 2 if document_ids else top_k,
            filter_metadata or None,
        )
        if document_ids:
            results = [
                r
                for r in results
                if r["metadata"].get("document_id") in document_ids
            ]
        return results[:top_k]

    async def generate_answer(
        self,
        query: str,
        context: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not context:
            return {
                "answer": (
                    "Xin lỗi, tôi không tìm thấy thông tin liên quan "
                    "để trả lời câu hỏi của bạn."
                ),
                "sources": [],
                "confidence": 0.0,
            }

        answer = self._generate_simple_answer(query, context)
        sources = [
            {
                "document_id": item["metadata"]["document_id"],
                "filename": item["metadata"]["filename"],
                "chunk_index": item["metadata"]["chunk_index"],
                "similarity": item["similarity"],
                "text_preview": item["metadata"]["chunk_text"][:200] + "...",
            }
            for item in context
        ]
        return {
            "answer": answer,
            "sources": sources,
            "confidence": float(context[0]["similarity"]),
        }

    def _generate_simple_answer(
        self,
        query: str,
        context: List[Dict[str, Any]],
    ) -> str:
        most_relevant = context[0]["metadata"]["chunk_text"]
        answer = (
            "Dựa trên tài liệu, tôi có thể cung cấp thông tin sau:\n"
            f"{most_relevant}\n"
            f'Thông tin này được trích xuất từ tài liệu '
            f'"{context[0]["metadata"]["filename"]}".'
        )
        if len(context) > 1:
            answer += (
                f"\n\nCó thêm {len(context) - 1} nguồn thông tin "
                "liên quan khác trong tài liệu."
            )
        return answer

    # ------------------------------------------------------------------ #
    # Summarization
    # ------------------------------------------------------------------ #
    async def summarize_document(
        self,
        document_id: str,
        user_id: str,
        max_length: int = 500,
    ) -> str:
        sample_query = "overview summary content"
        query_embedding = await asyncio.to_thread(
            self.embedding_generator.encode_query, sample_query
        )
        results = await asyncio.to_thread(
            self.vector_db.search,
            query_embedding,
            10,
            {"document_id": document_id, "user_id": user_id},
        )
        if not results:
            raise ValueError("Document not found or access denied")

        all_text = " ".join(
            r["metadata"]["chunk_text"]
            for r in sorted(
                results, key=lambda x: x["metadata"]["chunk_index"]
            )
        )
        return self._generate_simple_summary(all_text, max_length)

    def _generate_simple_summary(self, text: str, max_length: int) -> str:
        summary = ""
        for sentence in text.split(". "):
            if len(summary) + len(sentence) > max_length:
                break
            summary += sentence + ". "
        return summary.strip()

    # ------------------------------------------------------------------ #
    # Maintenance
    # ------------------------------------------------------------------ #
    async def delete_document_vectors(self, document_id: str) -> int:
        return await asyncio.to_thread(
            self.vector_db.delete_where, {"document_id": document_id}
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "vector_db_stats": self.vector_db.get_stats(),
            "embedding_model": self.embedding_generator.model_name,
            "embedding_dimension": self.embedding_generator.get_dimension(),
        }


_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
