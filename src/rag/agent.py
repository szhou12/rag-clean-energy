# src/rag/agent.py
from typing import Optional
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from rag.embedders import OpenAIEmbedding, BgeEmbedding
from rag.vector_stores import ChromaVectorStore
from rag.custom_retriever import BilingualRetriever


class RAGAgent:
    def __init__(
            self,
            llm: str = "gpt-4o-mini",
            vector_db_persist_dir: Optional[str] = None, 
            response_template: Optional[str] = None 
    ) -> None:
        """
        Initialize the RAGAgent class.
        Responsibility:
            1. Intake user's query
            2. Retrieve relevant documents from Chroma
            3. Generate a response using the language model
        
        :param llm: (str) - Name of the language model (e.g., "gpt-4o-mini")
        :param vector_db_persist_dir: (str | None) - Name of Chroma's persistent directory inside a docker container. Used to construct persistent directory. If None, storage is in-memory and emphemeral.
        :param response_template: (str | None) - Predefined template for formatting responses
        :return: None
        """

        if response_template:
            self.response_template = response_template
        else:
            self.response_template = """
                No matter user's query is in English or Chinese, the response should be in Chinese! \n
                Your response should be in a format of a report that follows the below structure enclosed by <format></format>: \n

                <format>\n
                Title: give a proper title. \n\n
                Summary: give a brief highlighted summary. \n\n
                Details: provide detailed content and enrich the details with numbers and statistics. 
                For any numbers or statistics you provide, please cite the source in brackets by extracting the content enclosed by <source><\source> . DO NOT include the tag <source><\source> itself. \n\n
                Conclusion: give a proper conclusion. \n
                </format>\n

                At the end of the report, please provide a list of references from the tag <source><\source> ONLY for cited sources used in Details section. 
                DO NOT duplicate refereces.
                DO NOT include the tag <source><\source> itself. 
                The whole report MUST be in Chinese.
                """

            
        # TODO: modify the way to write it later
        self.llm = ChatOpenAI(
            model=llm,
            temperature=0,
        )

        ## Embedding models to convert texts to embeddings (vectors)
        self.embedders = {
            "openai": OpenAIEmbedding().model,
            "bge_en": BgeEmbedding(model_name="BAAI/bge-small-en-v1.5").model,
            "bge_zh": BgeEmbedding(model_name="BAAI/bge-small-zh-v1.5").model,
        }

        self.vector_stores = {
            "en": ChromaVectorStore(
                collection_name="docs_en",  # English collection
                embedding_model=self.embedders['bge_en'],
                persist_directory=vector_db_persist_dir,
            ),
            "zh": ChromaVectorStore(
                collection_name="docs_zh",  # Chinese collection
                embedding_model=self.embedders['bge_zh'],
                persist_directory=vector_db_persist_dir,
            ),
        }
    

    def handle_query(self, user_query, chat_history):
        """
        Handle a user query by retrieving relevant information and formatting a contextual response by referring to the chat history.
        Workflow:
            user query -> _retrieve_contextual_docs() retrieve relevant docs (cost point) -> _format_response() format response (cost point)
        
        :param query: The user's query
        :param chat_history: The chat history
        :return: Formatted response to the query
        """
        # Step 1: Retrieve relevant chunks from the vector store
        # TODO deprecate: relevant_chunks = self._retrieve_contextual_docs()
        relevant_chunks = self._retrieve_bilingual_contextual_docs()
        
        # Step 2: Format the response using the predefined template
        retrieval_chain = self._format_response(relevant_chunks)

        # Step 3: Stream the response
        answer_only_retrieval_chain = retrieval_chain.pick("answer") # .pick() keeps only key="answer" in the response
        response = answer_only_retrieval_chain.stream({
            "chat_history": chat_history,
            "input": user_query
        })

        # return response["answer"] # use this if use retrieval_chain.invoke()
        return response
    
    ## TODO: deprecate
    # def _retrieve_contextual_docs(self):
    #     """
    #     Retrieve relevant documents from the vector store based on the chat history and the user's query.
    #     1. This function first looks at the chat history and the current user's question.
    #     2. It then uses the LLM to reformulate the question if necessary. e.g., user query "Please explain green hydrogen to me" might be transformed to "What is green hydrogen and how does it relate to renewable energy sources?" This reformulation takes into account the previous conversation about renewable energy sources.
    #     3. The reformulated question is then used to retrieve relevant documents from the vector store. In our example, it retrieved three key pieces of information about green hydrogen.

    #     :return: Runnable[Any, List[Document]] - An LCEL Runnable. The Runnable output is a list of Documents. For simple understanding, returned is a list of relevant documents retrieved from the vector store
    #     """
    #     if not self.vector_store:
    #         raise ValueError("Vector store is not initialized. Cannot create retriever chain.")
        
    #     vector_store_retriever = self.vector_store.as_retriever()

    #     contextualize_q_system_prompt = (
    #         "Given a chat history and the latest user question "
    #         "which might reference context in the chat history, "
    #         "formulate a standalone question which can be understood "
    #         "without the chat history. Do NOT answer the question, "
    #         "just reformulate it if needed and otherwise return it as is."
    #     )

    #     prompt = ChatPromptTemplate.from_messages([
    #         ("system", contextualize_q_system_prompt),
    #         MessagesPlaceholder(variable_name="chat_history"),
    #         ("human", "{input}"),
    #     ])

    #     retrieved_docs = create_history_aware_retriever(self.llm, vector_store_retriever, prompt)
    #     return retrieved_docs
    
    def _retrieve_bilingual_contextual_docs(self):
        """
        Retrieve relevant documents from both English and Chinese vector stores based on the chat history and the user's query.
        1. This function first looks at the chat history and the current user's question.
        2. It then uses the LLM to reformulate the question if necessary. 
        e.g., user query "Please explain green hydrogen to me" might be transformed to 
        "What is green hydrogen and how does it relate to renewable energy sources?" This reformulation takes into account the previous conversation about renewable energy sources.
        3. The reformulated question is then used to retrieve relevant documents from both the English and Chinese vector stores.

        :return: Runnable[Any, List[Document]] - An LCEL Runnable. The Runnable output is a list of Documents from both collections.
        """
        # Ensure both vector stores are initialized
        if not self.vector_stores['en'] or not self.vector_stores['zh']:
            raise ValueError("Vector stores for both Chinese and English must be initialized.")
        
        # Create retrievers for English and Chinese vector stores
        english_retriever = self.vector_stores['en'].as_retriever()
        chinese_retriever = self.vector_stores['zh'].as_retriever()

        # Initialize the bilingual retriever with both English and Chinese retrievers
        bilingual_retriever = BilingualRetriever(english_retriever=english_retriever, 
                                                 chinese_retriever=chinese_retriever)

        # Define the prompt to contextualize the query using the chat history
        contextualize_q_system_prompt = (
            "Given a chat history and the latest user question "
            "which might reference context in the chat history, "
            "formulate a standalone question which can be understood "
            "without the chat history. Do NOT answer the question, "
            "just reformulate it if needed and otherwise return it as is.\n"
            "根据聊天记录和最新的用户问题，请将最新的用户问题重新表述为一个可以在没有聊天记录的情况下理解的独立问题。"
            "不要回答问题，只需要重新表述即可。如果没有必要重新表述，则原样返回问题。"
        )

        # Create the prompt template using LangChain's ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        # Use create_history_aware_retriever to chain the LLM with the bilingual retriever
        retrieved_docs = create_history_aware_retriever(self.llm, bilingual_retriever, prompt)

        return retrieved_docs

    
    def _format_response(self, retrieved_docs):
        """
        Format the retrieved chunks into a coherent response based on a response template.
        1. This function takes the retrieved documents (retrieved_docs), the current user's query, and the chat history.
        2. It then uses another LLM call to generate a structured response based on the provided template.
        3. The LLM combines the retrieved information with its own knowledge to create a comprehensive, structured response to user's query.
        4. The final response will be in the format of the response template provided during initialization.

        :param retrieved_docs: List of text chunks retrieved from the vector store
        :return: An LCEL Runnable. The Runnable return is a dictionary containing at the very least a context and answer key.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Combine the given chat history and the following pieces of retrieved context to answer the user's question.\n<retrieved context>{context}</retrieved context>"), # context = retrieved_docs
            ("system", self.response_template),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "<user query>{input}</user query>"), # input = user query
        ])
        stuff_documents_chain = create_stuff_documents_chain(self.llm, prompt)
        retrieval_chain = create_retrieval_chain(retrieved_docs, stuff_documents_chain)
        return retrieval_chain


