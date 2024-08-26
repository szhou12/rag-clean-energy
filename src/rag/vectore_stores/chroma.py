# project/src/rag/vector_stores/chroma.py
import os
from uuid import uuid4
from langchain_chroma import Chroma
from langchain_community.vectorstores.utils import filter_complex_metadata
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

    def add_documents(self, documents):
        '''
        Add documents to the vector store.
        Note: if the input documents contains ids and also give .add_documents() ids in the kwargs (ids=uuids), then ids=uuids will take precedence. Think of each given uuid as unique identifier of one record stored in Database.

        :param documents: List[Document]
        :return: List[str] UUIDs of the added documents
        '''
        uuids = [str(uuid4()) for _ in range(len(documents))]
        return self.vector_store.add_documents(documents=filter_complex_metadata(documents), ids=uuids)
    
    def as_retriever(self, **kwargs):
        '''
        Wrapper of as_retriever() method of Chroma class.
        Ref: https://python.langchain.com/v0.2/api_reference/chroma/vectorstores/langchain_chroma.vectorstores.Chroma.html#langchain_chroma.vectorstores.Chroma.as_retriever
        '''
        return self.vector_store.as_retriever(**kwargs)
    
    # TODO
    def similarity_search(self, query, k=4):
        # return self.vector_store.similarity_search(query, k=k)
        pass
    
    # TODO
    def delete(self, ids):
        # self.vector_store.delete(ids)
        pass

    