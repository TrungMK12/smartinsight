from fastapi import APIRouter
from backend.app.engine.llm import LlmOlama
from mini_vector_db.vector_db import MiniVectorBase

router = APIRouter(
    prefix="/chat"
)

VECTOR_DIR = "backend/data/vectors"

vb = MiniVectorBase()
llm = LlmOlama()

@router.post("/")
async def getResponse(file_name: str, query: str, top_k: int = 3):
    try:
        vb.load(f"{VECTOR_DIR}/{file_name}_vector")
    except Exception as e:
        return {"error": f"Failed to load vector database: {str(e)}"}
    results = vb.search(query, top_k)
    chat_history = []
    if len(chat_history) >= 3:
        query = await llm.rewrite_query(user_query=query, chat_history=chat_history)
    response = await llm.generate_rag(user_query=query, context=results)
    chat_history.append({"role": "user", "content": query})
    chat_history.append({"role": "assistant", "content": response})
    return {"response": response}

    

