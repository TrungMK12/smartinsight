from backend.app.core.config import settings
from backend.app.engine.embedding import get_embedding_generator
from backend.app.engine.processor import DocumentProcessor
from mini_vector_db.vector_db import MiniVectorBase

class Rag:
    def __init__(self):
        self.vector_database = MiniVectorBase()
        self.processor = DocumentProcessor()
        self.embedding = get_embedding_generator()

    async def document_proccessing(
        self,
        file_content: bytes,
        filename: str,
        file_type: str,
        user_id: str,
        document_id: str
    ):
        if file_type == "pdf":
            text = self.document_processor.process_pdf(file_content)
        elif file_type == "docx":
            text = self.document_processor.process_docx(file_content)
        elif file_type == "txt":
            text = self.document_processor.process_txt(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        chunks = self.processor.chunk_text(
            text=text,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap
        )
        if not chunks:
            raise ValueError("No text content extracted from document")
        embedding = self.embedding.encode_text(text=text)
        metadata = [
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
        vector_id = self.vector_database.add(
            embedding=embedding,
            metadata=metadata
        )
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
        
