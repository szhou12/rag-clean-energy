# project/src/rag/vector_stores/chroma.py
import os
from langchain_chroma import Chroma
from .base_vectore_store import VectorStore

class ChromaVectorStore(VectorStore):
    def __init__(self, embedding_model, collection_name, persist_db_name=None):
        super().__init__(embedding_model)

        self._persist_directory = None

        if persist_db_name is not None:
            full_path = os.path.join(os.getcwd(), persist_db_name)
            # If persist_directory is provided but doesn't exist, create it
            if not os.path.exists(full_path):
                os.makedirs(full_path, exist_ok=True)
            self._persist_directory = full_path

        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embedding_model,
            persist_directory=self._persist_directory,
        )

    def add_texts(self, texts, metadatas=None):
        self.vector_store.add_texts(texts=texts, metadatas=metadatas)

    def similarity_search(self, query, k=4):
        return self.vector_store.similarity_search(query, k=k)

    def delete(self, ids):
        self.vector_store.delete(ids)

    def persist(self):
        self.vector_store.persist()

    def as_retriever(self, **kwargs):
        return self.vector_store.as_retriever(**kwargs)