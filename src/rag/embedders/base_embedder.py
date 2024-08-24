# rag/embedders/base_embedder.py

from abc import ABC

class BaseEmbeddingModel(ABC):
    def __init__(self):
        self.model = None  # Placeholder for the actual embedding model