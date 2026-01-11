from backend.app.engine.vector_db import MiniVectorBase
from backend.app.engine.llm import LlmOlama
from backend.app.engine.processor import clean_text, chunking_text
import time

start = time.perf_counter()
chunks = chunking_text(clean_text("pdf", r""))
t1 = time.perf_counter()
print("A mất:", t1 - start, "giây")

vb = MiniVectorBase()
t2 = time.perf_counter()
print("B mất:", t2 - t1, "giây")

for chunk in chunks:
    vb.add(chunk)
t3 = time.perf_counter()
print("C mất:", t3 - t2, "giây")

query = "Research Experience?"

results = vb.search(query, top_k=3)
t4 = time.perf_counter()
print("D mất:", t4 - t3, "giây")

llm = LlmOlama()
t5 = time.perf_counter()
print("E mất:", t5 - t4, "giây")

response = llm.generate_rag(user_query=query, context=results)
t6 = time.perf_counter()
print("F mất:", t6 - t5, "giây")
