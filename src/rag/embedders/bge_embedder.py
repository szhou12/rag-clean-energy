from rag.embedders.base_embedder import BaseEmbeddingModel
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

class BgeEmbedding(BaseEmbeddingModel):
    def __init__(self, model_name: str):
        """
        Initialize the BgeEmbedding model with a specified model_name.

        :param model_name: The name of the Hugging Face model to be used for Chines/English embedding.
        """
        super().__init__()

        model_kwargs = {"device": "cpu"} # TODO: may need to change after deploy to cloud
        encode_kwargs = {"normalize_embeddings": True} # set True to compute cosine similarity

        self.model = HuggingFaceBgeEmbeddings(
            model_name=model_name, 
            model_kwargs=model_kwargs, 
            encode_kwargs=encode_kwargs
        )
    