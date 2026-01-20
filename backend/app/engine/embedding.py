import numpy as np
from typing import List, Union
from sentence_transformers import SentenceTransformer
from app.core.config import settings

class EmbeddingGenerator:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.vector_modelname
        self.model = None
        self._load_model()
    
    def _load_model(self):
        try:
            self.model = SentenceTransformer(self.model_name)
        except Exception as e:
            raise
    
    def encode_text(self, text: Union[str, List[str]]) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Embedding model not loaded")
        if isinstance(text, str):
            text = [text]
        embeddings = self.model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        return embeddings
    
    def encode_query(self, query: str) -> np.ndarray:
        embedding = self.encode_text(query)
        return embedding[0] if len(embedding.shape) > 1 else embedding
    
    def get_dimension(self) -> int:
        if self.model is None:
            raise RuntimeError("Embedding model not loaded")
        return self.model.get_sentence_embedding_dimension()

_embedding_generator: EmbeddingGenerator = None

def get_embedding_generator() -> EmbeddingGenerator:
    global _embedding_generator
    
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    
    return _embedding_generator