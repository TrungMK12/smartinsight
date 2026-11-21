"""Client gọi Ollama (async) cho sinh câu trả lời RAG."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Lỗi khi gọi LLM (timeout, mất kết nối, response rỗng...)."""


class OllamaLLM:
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.model_name = model_name or settings.llm_modelname
        self.base_url = (base_url or settings.llm_baseurl).rstrip("/")
        self.timeout = timeout or settings.llm_timeout

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": options
            or {"temperature": temperature if temperature is not None else settings.llm_temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat", json=payload
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            raise LLMError(f"Không gọi được Ollama tại {self.base_url}: {e}") from e
        except ValueError as e:
            raise LLMError(f"Ollama trả về JSON không hợp lệ: {e}") from e

        content = (data.get("message") or {}).get("content", "")
        content = (content or "").strip()
        if not content:
            raise LLMError("Ollama trả về nội dung rỗng")
        return content

    async def rewrite_query(
        self,
        user_query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Viết lại câu hỏi follow-up thành câu độc lập dựa trên lịch sử."""
        if not chat_history:
            return user_query

        recent = chat_history[-4:]
        history_str = "\n".join(
            f"{'Người dùng' if m.get('role') == 'user' else 'Trợ lý'}: {m.get('content', '')}"
            for m in recent
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "Bạn viết lại câu hỏi của người dùng thành một câu hỏi độc lập, "
                    "đầy đủ ngữ cảnh để dùng cho tìm kiếm tài liệu. "
                    "Giữ nguyên ngôn ngữ, không giải thích, chỉ trả về câu hỏi đã viết lại."
                ),
            },
            {
                "role": "user",
                "content": f"LỊCH SỬ:\n{history_str}\n\nCÂU HỎI MỚI: {user_query}",
            },
        ]
        try:
            rewritten = await self.chat(messages, temperature=0.0)
        except LLMError:
            logger.warning("rewrite_query thất bại, dùng câu hỏi gốc", exc_info=True)
            return user_query

        rewritten = rewritten.strip().strip('"').strip()
        return rewritten or user_query

    async def generate_rag(self, user_query: str, context: List[str]) -> str:
        context_str = "\n\n".join(
            f"[Nguồn {i + 1}]: {chunk}" for i, chunk in enumerate(context)
        )
        messages = [
            {"role": "system", "content": settings.llm_system_prompt},
            {
                "role": "user",
                "content": (
                    f"NGỮ CẢNH:\n{context_str}\n\n"
                    f"CÂU HỎI: {user_query}\n\n"
                    "Hãy trả lời chỉ dựa trên ngữ cảnh trên. "
                    "Trích dẫn nguồn dạng [Nguồn i] khi sử dụng thông tin. "
                    "Nếu ngữ cảnh không có thông tin, hãy nói rõ điều đó."
                ),
            },
        ]
        return await self.chat(messages)


# Tên cũ để không phá vỡ code đang import
LlmOlama = OllamaLLM

_llm: Optional[OllamaLLM] = None


def get_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM()
    return _llm
