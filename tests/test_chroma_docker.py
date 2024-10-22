from uuid import uuid4
from typing import Optional, List, Dict
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from chromadb import HttpClient
from langchain.schema import Document
from langchain_chroma import Chroma
from langchain_community.vectorstores.utils import filter_complex_metadata
from rag.embedders import OpenAIEmbedding
from rag.vector_stores import ChromaVectorStore

load_dotenv()


if __name__ == "__main__":
    test_persist_directory = "/data/chroma"


    # base_dir = "/Users/shuyuzhou/Documents/github/rag-clean-energy"
    # if test_persist_directory is not None:
    #     # full_path is the directory in host machine that is mounted to the container's persist_directory
    #     full_path = os.path.join(base_dir, test_persist_directory)
    #     print(f"host machine persistent directory: {full_path}")
    #     # Create the directory if it doesn't exist
    #     if not os.path.exists(full_path):
    #         os.makedirs(full_path, exist_ok=True)
            
    embedding_model = OpenAIEmbedding().model
    chroma_store = ChromaVectorStore(
                collection_name="docs_en",  # English collection
                embedding_model=embedding_model,
                host="localhost",
                port=8000,
                persist_directory=test_persist_directory,
            )
    
    # Add documents to the vector store
    documents = [
        Document(page_content="Some text", metadata={"source": "iea.org", "page": 1}),
        Document(page_content="More text", metadata={"source": "iea.org", "page": 2})
    ]
    
    added_docs = chroma_store.add_documents(documents)

    print(f"Added documents: {added_docs}")

    # Retrieve documents by IDs
    ids = [x['id'] for x in added_docs]

    # ids = ['e9b8d0a5-6e76-4668-ba74-21f32e6e95ce', '90727601-7a67-4782-b9ad-cd2e70341477']
    retrieved_docs = chroma_store.get_documents_by_ids(ids)

    print(f"Retrieved documents: {retrieved_docs}")
    
    # docker pull chromadb/chroma
    # docker run -p 8000:8000 -v /Users/shuyuzhou/Documents/github/rag-clean-energy/data/chroma:/data/chroma chromadb/chroma
    # docker run --name='chroma_container' -d -p 8000:8000 chromadb/chroma
    