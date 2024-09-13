# project/src/rag/vector_stores/chroma.py
import os
from uuid import uuid4
from typing import Optional
from langchain_chroma import Chroma
from langchain_community.vectorstores.utils import filter_complex_metadata
from .base_vectore_store import VectorStore

class ChromaVectorStore(VectorStore):
    def __init__(self, collection_name, embedding_model, persist_db_name=None):
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

    def as_retriever(self, **kwargs):
        """
        Wrapper of as_retriever() method of Chroma class.
        Ref: https://python.langchain.com/v0.2/api_reference/chroma/vectorstores/langchain_chroma.vectorstores.Chroma.html#langchain_chroma.vectorstores.Chroma.as_retriever
        """
        return self.vector_store.as_retriever(**kwargs)

    def add_documents(self, documents, ids: Optional[list[str]] = None):
        """
        Add documents to the vector store.
        Note: if the input documents contains ids and also give .add_documents() ids in the kwargs (ids=uuids), then ids=uuids will take precedence.
        Think of each given uuid as unique identifier of one record stored in Database.

        :param documents: List[Document]
        :param ids: List[str] (optional) - Predefined UUIDs for the documents. If None or length mismatch, new UUIDs will be generated.
        :return: List[dict] [{'id': uuid4, 'source': source}, {...}]
        :raises: RuntimeError if the embedding insertion fails or document's source is not found.
        """
        try:
            if ids is None or len(ids) != len(documents):
                uuids = [str(uuid4()) for _ in range(len(documents))]
            else:
                uuids = ids

            # Generate UUIDs and extract sources
            document_info_list = []
            
            for doc, uuid in zip(documents, uuids):
                source = doc.metadata.get('source', None)  # file parser and scraper class will ensure 'source' NOT None
                if source is None:
                    raise ValueError(f"Missing 'source' in document metadata for document {doc}")
                
                document_info_list.append({'id': uuid, 'source': source})

            # Attempt to add documents to the vector store
            self.vector_store.add_documents(documents=filter_complex_metadata(documents), ids=uuids)

            return document_info_list

        except Exception as e:
            # Catch any errors and raise them as RuntimeError with context information
            raise RuntimeError(f"Failed to add documents to Chroma: {e}")

    
    def delete(self, ids: list[str]):
        """
        Delete documents by assigned ids from the vector store.

        :param ids: list[str] List of uuid4 to identify the documents to be deleted.
        :raises: Exception if deletion fails.
        """
        try:
            self.vector_store.delete(ids=ids)
        except Exception as e:
            raise RuntimeError(f"Error while deleting from Chroma: {e}")
        
    def get_documents_by_ids(self, ids: list[str]):
        """
        Retrieve documents from the vector store by their unique IDs using Chroma's `get_by_ids`.

        :param ids: List of document IDs to retrieve.
        :return: List of Document objects corresponding to the provided IDs.
        :raises: RuntimeError if document retrieval fails.
        """
        try:
            documents = self.vector_store.get_by_ids(ids=ids)
            return documents
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve documents by IDs from Chroma: {e}")

    # TODO
    def similarity_search(self, query, k=4):
        # return self.vector_store.similarity_search(query, k=k)
        pass

    