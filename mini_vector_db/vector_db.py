from backend.app.core.config import settings
from sentence_transformers import SentenceTransformer
import numpy as np
import json

class MiniVectorBase:
    def __init__(self, model_name: str = settings.vector_modelname):
        self.model = SentenceTransformer(model_name)
        self.vector = None
        self.metadata = []
    
    def add(self, chunk: str):
        embedding = self.model.encode(chunk)
        if self.vector is None:
            self.vector = embedding
        else:
            self.vector = np.vstack([self.vector, embedding])
        self.metadata.append(chunk)

    def search(self, query: str, top_k=3):
        if self.vector is None:
            return 
        query_vector = self.model.encode(query)
        similarity = []
        dot = np.dot(self.vector, query_vector)
        norm_query = np.linalg.norm(query_vector)
        norm_vectors = np.linalg.norm(self.vector, axis=1)
        simi = dot / (norm_vectors * norm_query + 1e-10)
        for idx, score in enumerate(simi):
            similarity.append((self.metadata[idx], score))
        similarity.sort(key=lambda x: x[1], reverse=True)
        return similarity[:top_k]
    
    def save(self, file_path: str):
        np.save(file_path + ".vectors.npy", self.vector)
        with open(file_path + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False)

    def load(self, file_path):
        self.vector = np.load(file_path + ".vectors.npy")
        with open(file_path + ".meta.json", "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
