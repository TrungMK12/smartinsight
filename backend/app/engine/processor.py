import io
from typing import List, Dict, Any
import PyPDF2
from docx import Document

class DocumentProcessor:
    @staticmethod
    def process_pdf(file_content: bytes) -> str:
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n\n"
            return text.strip()
        except Exception as e:
            raise ValueError(f"Failed to process PDF: {str(e)}")
    
    @staticmethod
    def process_docx(file_content: bytes) -> str:
        try:
            doc = Document(io.BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise ValueError(f"Failed to process DOCX: {str(e)}")
    
    @staticmethod
    def process_txt(file_content: bytes) -> str:
        try:
            return file_content.decode('utf-8').strip()
        except UnicodeDecodeError:
            for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    return file_content.decode(encoding).strip()
                except UnicodeDecodeError:
                    continue
            raise ValueError("Failed to decode text file")
    
    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> List[str]:
        if not text:
            return []
        chunks = []
        start = 0
        text_length = len(text)
        while start < text_length:
            end = start + chunk_size
            if end < text_length:
                for punct in ['. ', '! ', '? ', '\n\n']:
                    last_punct = text[start:end].rfind(punct)
                    if last_punct != -1:
                        end = start + last_punct + len(punct)
                        break
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - chunk_overlap if end < text_length else text_length
        return chunks
    
    @staticmethod
    def extract_metadata(
        filename: str,
        file_size: int,
        file_type: str,
        text: str
    ) -> Dict[str, Any]:
        words = text.split()
        return {
            "filename": filename,
            "file_size": file_size,
            "file_type": file_type,
            "word_count": len(words),
            "char_count": len(text),
            "preview": text[:200] + "..." if len(text) > 200 else text
        }
