from rag.embedders.base_embedder import BaseEmbeddingModel
from dotenv import load_dotenv
import os
from langchain_openai import OpenAIEmbeddings

load_dotenv() # Load OPENAI_api_key as environment variable from .env file

class OpenAIEmbedding(BaseEmbeddingModel):
    def __init__(self):
        super().__init__()  # Initialize the base class

        api_key = os.getenv('OPENAI_API_KEY')  # Load API key from environment
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

        self.model = OpenAIEmbeddings()  # Assign the Langchain OpenAI client to self.model
