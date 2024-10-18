import os
from typing import Optional
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from rag.embedders.base_embedder import BaseEmbeddingModel

load_dotenv() # Load OPENAI_api_key as environment variable from .env file

class OpenAIEmbedding(BaseEmbeddingModel):
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the OpenAI embedding model with a specified model_name.

        :param model_name: The name of the OpenAI embedding model to be used. If None, default model is text-embedding-ada-002.
        """
        super().__init__()  # Initialize the base class

        api_key = os.getenv('OPENAI_API_KEY')  # Load API key from environment
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
        
        if model_name is None:
            self.model = OpenAIEmbeddings(api_key=api_key)
        else:
            self.model = OpenAIEmbeddings(model=model_name, api_key=api_key)
