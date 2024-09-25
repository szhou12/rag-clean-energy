from typing import List
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
import asyncio
from pydantic import Field

class BilingualRetriever(BaseRetriever):
    """Custom retriever that retrieves relevant documents from both English and Chinese collections."""

    # Use Field(...) to indicate that these fields are required but don't have default values.
    english_retriever: BaseRetriever = Field(...)
    chinese_retriever: BaseRetriever = Field(...)

    def __init__(self, english_retriever: BaseRetriever, chinese_retriever: BaseRetriever):
        """
        Initialize with two retrievers: one for English-based content and one for Chinese-based content.
        
        :param english_retriever: The retriever responsible for English documents.
        :param chinese_retriever: The retriever responsible for Chinese documents.
        """
        # Pass the retrievers to the super().__init__() call, which initializes the Pydantic model correctly.
        super().__init__(english_retriever=english_retriever, chinese_retriever=chinese_retriever)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        Retrieve relevant documents from both English and Chinese retrievers.
        
        :param query: The query string to retrieve relevant documents for.
        :param run_manager: The callback manager to handle retriever runs.
        :return: A list of relevant documents from both collections.
        """
        # Retrieve documents from both English and Chinese retrievers
        english_docs = self.english_retriever._get_relevant_documents(query, run_manager=run_manager)
        chinese_docs = self.chinese_retriever._get_relevant_documents(query, run_manager=run_manager)
        
        # Combine both sets of documents into a single list
        combined_docs = english_docs + chinese_docs

        return combined_docs

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        Asynchronously retrieve relevant documents from both English and Chinese retrievers.
        
        :param query: The query string to retrieve relevant documents for.
        :param run_manager: The callback manager to handle retriever runs.
        :return: A list of relevant documents from both collections.
        """
        # Retrieve documents from both English and Chinese retrievers asynchronously

        # english_docs = await self.english_retriever._aget_relevant_documents(query, run_manager=run_manager)
        # chinese_docs = await self.chinese_retriever._aget_relevant_documents(query, run_manager=run_manager)

        english_docs, chinese_docs = await asyncio.gather(
            self.english_retriever._aget_relevant_documents(query, run_manager=run_manager),
            self.chinese_retriever._aget_relevant_documents(query, run_manager=run_manager)
        )

        # Combine both sets of documents into a single list
        combined_docs = english_docs + chinese_docs

        return combined_docs