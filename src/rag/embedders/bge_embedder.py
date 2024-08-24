from rag.embedders.base_embedder import BaseEmbeddingModel
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

class HuggingFaceBgeEmbedding(BaseEmbeddingModel):
    def __init__(self):
        super().__init__()

        model_name = "BAAI/bge-large-zh-v1.5" # For Chinese embedding
        model_kwargs = {"device": "cpu"}
        encode_kwargs = {"normalize_embeddings": True} # set True to compute cosine similarity

        self.model = HuggingFaceBgeEmbeddings(
            model_name=model_name, 
            model_kwargs=model_kwargs, 
            encode_kwargs=encode_kwargs
        )
    