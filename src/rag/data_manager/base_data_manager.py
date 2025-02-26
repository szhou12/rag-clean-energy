from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Optional, Literal, List, Tuple, Generator
from db_mysql import MySQLManager
from rag.parsers import PDFParser, ExcelParser
from rag.scrapers import WebScraper
from rag.embedders import OpenAIEmbedding, BgeEmbedding
from rag.vector_stores import ChromaVectorStore
from rag.text_processor import TextProcessor

class BaseDataManager(ABC):
    """
    Base class for RAG pipeline - data management
    """
    def __init__(self, mysql_config: dict, vector_db_persist_dir: Optional[str] = None) -> None:
        self.mysql_manager = MySQLManager(**mysql_config)
        self.vector_stores = self._init_vector_stores(vector_db_persist_dir)
        self.text_processor = TextProcessor()

    @abstractmethod
    def process(self):
        """
        Main processing method to be implemented by subclasses
        """
        pass

    def _init_vector_stores(self, persist_dir: str) -> dict:
        """
        Chroma vector store initialization
        """
        return {
            "en": ChromaVectorStore(
                collection_name="docs_en",  # English collection
                embedding_model=self.embedders['bge_en'],
                # embedding_model=self.embedders['openai'],
                persist_directory=persist_dir,
            ),
            "zh": ChromaVectorStore(
                collection_name="docs_zh",  # Chinese collection
                embedding_model=self.embedders['bge_zh'],
                # embedding_model=self.embedders['openai'],
                persist_directory=persist_dir,
            ),
        }
    
    def _init_embedder(self) -> dict:
        """
        Embedding model initialization
        """
        return {
            "openai": OpenAIEmbedding().model,
            # "bge_en": BgeEmbedding(model_name="BAAI/bge-small-en-v1.5").model,
            # "bge_zh": BgeEmbedding(model_name="BAAI/bge-small-zh-v1.5").model,
            "bge_en": BgeEmbedding(model_name="BAAI/bge-base-en-v1.5").model,
            "bge_zh": BgeEmbedding(model_name="BAAI/bge-base-zh-v1.5").model,
            # "bge_en": BgeEmbedding(model_name="BAAI/bge-large-en-v1.5").model,
            # "bge_zh": BgeEmbedding(model_name="BAAI/bge-large-zh-v1.5").model,
        }
    
    @contextmanager
    def transaction(self):
        pass
