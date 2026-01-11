from backend.app.core.config import settings
import requests

class LlmOlama:
    def __init__(self, model_name: str = settings.llm_modelname, base_url: str = settings.llm_baseurl):
        self.model_name = model_name
        self.base_url = base_url

    def call_llm(self, messages: list[dict], options: dict = None):
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": options or {
                "temperature": 0.3,
            }
        }
        try:
            response = requests.post(url=url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()['message']['content']
        except Exception as e:
            return f"Error {str(e)}"
        
    def rewrite_query(self, user_query:str, chat_history: list[dict] = None):
        if not chat_history:
            return user_query
        
        recent_history = chat_history[-3:]
        history_str = ""
        for msg in recent_history:
            role = "Người dùng" if msg['role'] == 'user' else "Trợ lý"
            history_str += f"{role}: {msg['content']}\n"

        system_prompt = settings.llm_system_prompt
        user_content = f"LỊCH SỬ:\n{history_str}\nCÂU HỎI MỚI: {user_query}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        return self.call_llm(messages)
    
    def generate_rag(self, user_query: str, context: list):
        context_str = "\n\n".join([f"Đoạn văn bản: {chunk}\n" for chunk, score in context])
        prompt = f"Dựa trên các đoạn văn bản sau:\n{context_str}\nHãy trả lời câu hỏi sau một cách chi tiết và chính xác:\n{user_query}"
        
        messages = [
            {"role": "system", "content": "Bạn là một trợ lý AI giúp trả lời các câu hỏi dựa trên ngữ cảnh được cung cấp."},
            {"role": "user", "content": prompt}
        ]
        
        return self.call_llm(messages)
