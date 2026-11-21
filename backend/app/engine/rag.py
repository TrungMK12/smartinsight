import asyncio
import logging
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.engine.embedding import get_embedding_generator
from backend.app.engine.llm import LLMError, get_llm
from backend.app.engine.processor import DocumentProcessor
from backend.app.mini_vector_db.vector_db import MiniVectorBase

logger = logging.getLogger(__name__)

# Giới hạn ký tự đưa vào một lần gọi LLM khi tóm tắt
MAX_SUMMARY_INPUT_CHARS = 8000


class RAGEngine:
    def __init__(self) -> None:
        self.embedding_generator = get_embedding_generator()
        dimension = settings.vector_dimension or self.embedding_generator.get_dimension()
        self.vector_db = MiniVectorBase(
            storage_path=settings.vector_db_path,
            dimension=dimension,
        )
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

    async def rewrite_query(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        return await get_llm().rewrite_query(query, chat_history)

    # ------------------------------------------------------------------ #
    # Answer generation
    # ------------------------------------------------------------------ #
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

        context_chunks = [
            item["metadata"]["chunk_text"] for item in context
        ]
        try:
            answer = await get_llm().generate_rag(query, context_chunks)
        except LLMError:
            logger.warning(
                "LLM không khả dụng, dùng câu trả lời trích xuất", exc_info=True
            )
            answer = self._generate_simple_answer(query, context)

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
        chunks = await asyncio.to_thread(
            self.vector_db.get_metadata_where,
            {"document_id": document_id, "user_id": user_id},
        )
        if not chunks:
            raise ValueError("Document not found or access denied")

        ordered = sorted(chunks, key=lambda m: m.get("chunk_index", 0))
        full_text = "\n\n".join(m.get("chunk_text", "") for m in ordered)

        try:
            return await self._summarize_with_llm(full_text, max_length)
        except LLMError:
            logger.warning(
                "LLM không khả dụng, dùng tóm tắt trích xuất", exc_info=True
            )
            return self._generate_simple_summary(full_text, max_length)

    async def _summarize_with_llm(self, text: str, max_length: int) -> str:
        llm = get_llm()
        if len(text) <= MAX_SUMMARY_INPUT_CHARS:
            return await self._summarize_chunk(llm, text, max_length)

        parts = [
            text[i : i + MAX_SUMMARY_INPUT_CHARS]
            for i in range(0, len(text), MAX_SUMMARY_INPUT_CHARS)
        ]
        per_part = max(150, max_length // len(parts))
        partials = [
            await self._summarize_chunk(llm, part, per_part) for part in parts
        ]
        return await self._summarize_chunk(
            llm, "\n\n".join(partials), max_length
        )

    async def _summarize_chunk(self, llm, text: str, max_length: int) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Bạn là trợ lý tóm tắt tài liệu. Chỉ sử dụng thông tin "
                    "trong văn bản được cung cấp, trả lời bằng tiếng Việt."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Tóm tắt văn bản sau trong tối đa {max_length} ký tự. "
                    "Nêu các ý chính, không thêm thông tin ngoài văn bản.\n\n"
                    f"{text}"
                ),
            },
        ]
        return await llm.chat(messages)

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
