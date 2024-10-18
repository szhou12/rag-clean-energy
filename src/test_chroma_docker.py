import os
from uuid import uuid4
from typing import Optional, List, Dict
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from chromadb import HttpClient
from langchain.schema import Document
from langchain_chroma import Chroma
from langchain_community.vectorstores.utils import filter_complex_metadata
from rag.embedders import OpenAIEmbedding


load_dotenv()

class VectorStore(ABC):
    def __init__(self, embedding_model):
        """
        Initialize the VectorStore with an embedding model.
        
        :param embedding_model: An instance of an embedding model (e.g., OpenAIEmbedding, HuggingFaceBgeEmbedding)
        """
        self.embedding_model = embedding_model
        
    @abstractmethod
    def add_documents(self, documents):
        """
        Add texts and their metadata to the vector store.
        
        :param texts: List of text strings to add
        :param metadatas: List of metadata dictionaries corresponding to each text
        """
        pass

class ChromaVectorStore(VectorStore):
    def __init__(
            self,
            collection_name: str,
            embedding_model: str,
            host: str = "localhost",
            port: int = 8000,
            ssl: bool = False,
            headers: Optional[Dict[str, str]] = None,
            persist_directory: Optional[str] = None # Directory inside the container
    ):
        """
        Initialize the ChromaVectorStore class with HttpClient.

        :param collection_name: Name of the collection.
        :param embedding_model: The embedding model (e.g., OpenAI, BGE).
        :param chroma_host: Hostname or IP address where the Chroma server is running.
        :param chroma_port: Port where Chroma server is listening.
        :param ssl: Boolean to indicate if SSL is used for the connection.
        :param headers: Optional HTTP headers (metadata for HTTP requests) to pass to the Chroma server.
        """
        super().__init__(embedding_model)

        self._persist_directory = persist_directory
        self.collection_name = collection_name

        # TODO: Re-configure the directory after deploy to cloud
        # Set the hardcoded base directory
        # base_dir = "/Users/shuyuzhou/Documents/github/rag-clean-energy"
        # if persist_directory is not None:
        #     # Join the base directory with the persist_directory to create the full path
        #     full_path = os.path.join(base_dir, persist_directory)
        #     # Create the directory if it doesn't exist
        #     if not os.path.exists(full_path):
        #         os.makedirs(full_path, exist_ok=True)
        #     self._persist_directory = full_path

        # Initialize Chroma HttpClient
        self.http_client = HttpClient(
            host=host,
            port=port,
            ssl=ssl,
            headers=headers
        )

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=embedding_model,
            persist_directory=self._persist_directory,
            client=self.http_client,
        )

    def as_retriever(self, **kwargs):
        """
        Wrapper of as_retriever() method of Chroma class.
        """
        return self.vector_store.as_retriever(**kwargs)
    
    def get_documents_by_ids(self, ids: list[str]):
        """
        Retrieve documents from the vector store by their unique IDs using Chroma's `get`.

        :param ids: List of document IDs to retrieve.
        :return: List of Document objects corresponding to the provided IDs.
        :raises: RuntimeError if document retrieval fails.
        """
        try:
            # documents = self.vector_store.get_by_ids(ids)
            documents = self.vector_store.get(ids)['documents']
            return documents
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve documents by IDs from Chroma: {e}")

    def add_documents(self, documents: List[Document], ids: Optional[list[str]] = None, secondary_key: Optional[str] = None):
        """
        Add documents to the vector store.
        Note: if the input documents contains ids and also give .add_documents() ids in the kwargs (ids=uuids), then ids=uuids will take precedence.
        Think of each given uuid as unique identifier of one record stored in Database.

        :param documents: List[Document] - List of Document objects (chunks) to add to the vector store.
        :param ids: List[str] (optional) - Predefined UUIDs for the documents. If None or length mismatch, new UUIDs will be generated.
        :param secondary_key: str (optional) - Secondary key to be extracted from the document metadata. In the case of uploaded file pages, secondary key is 'page'.
        :return: List[dict] [{'id': uuid4, 'source': source}]
        :raises: RuntimeError if the embedding insertion fails or document's source is not found.
        """
        try:
            if ids is not None and len(ids) != len(documents):
                raise ValueError("The length of 'ids' must match the number of 'documents'.")
            # Fallback to generating UUIDs if not provided
            uuids = ids if ids is not None else [str(uuid4()) for _ in range(len(documents))]

            # Generate UUIDs and extract sources
            document_info_list = []
            
            for doc, uuid in zip(documents, uuids):
                source = doc.metadata.get('source', None)  # file parser and scraper class will ensure 'source' NOT None
                if not source:
                    raise ValueError(f"Missing 'source' (None or empty str) in document metadata for document {doc.metadata}")
                
                atom = {'id': uuid, 'source': source}

                # Augment chunk metadata with secondary key if provided
                if secondary_key is not None:
                    secondary_value = doc.metadata.get(secondary_key, None)
                    if secondary_value is None or secondary_value == "":
                        raise ValueError(f"Missing '{secondary_key}' (None or empty str) in document metadata for document {doc.metadata}")
                    atom[secondary_key] = str(secondary_value)

                document_info_list.append(atom)

            # Attempt to add documents to the vector store
            self.vector_store.add_documents(documents=filter_complex_metadata(documents), ids=uuids)

            print(f"Added {len(documents)} document chunks to Chroma in collection {self.collection_name}")

            return document_info_list

        except Exception as e:
            # Catch any errors and raise them as RuntimeError with context information
            raise RuntimeError(f"Failed to add documents to Chroma: {e}")


if __name__ == "__main__":
    test_persist_directory = "data/chroma"


    base_dir = "/Users/shuyuzhou/Documents/github/rag-clean-energy"
    if test_persist_directory is not None:
        # full_path is the directory in host machine that is mounted to the container's persist_directory
        full_path = os.path.join(base_dir, test_persist_directory)
        # Create the directory if it doesn't exist
        if not os.path.exists(full_path):
            os.makedirs(full_path, exist_ok=True)


    embedding_model = OpenAIEmbedding().model
    chroma_store = ChromaVectorStore(
                collection_name="docs_en",  # English collection
                embedding_model=embedding_model,
                host="localhost",
                port=8080,
                persist_directory=test_persist_directory,
            )
    
    # # Add documents to the vector store
    # documents = [
    #     Document(page_content="Some text", metadata={"source": "iea.org", "page": 1}),
    #     Document(page_content="More text", metadata={"source": "iea.org", "page": 2})
    # ]
    
    # added_docs = chroma_store.add_documents(documents)

    # print(f"Added documents: {added_docs}")

    # # Retrieve documents by IDs
    # ids = [x['id'] for x in added_docs]

    ids = ['e9b8d0a5-6e76-4668-ba74-21f32e6e95ce', '90727601-7a67-4782-b9ad-cd2e70341477']
    retrieved_docs = chroma_store.get_documents_by_ids(ids)

    print(f"Retrieved documents: {retrieved_docs}")
    
    # docker pull chromadb/chroma
    # docker run -p 8080:8000 -v /Users/shuyuzhou/Documents/github/rag-clean-energy/data/chroma:/data/chroma chromadb/chroma
    