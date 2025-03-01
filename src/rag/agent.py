# src/rag/agent.py
import logging
from typing import Optional
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock
from rag.embedders import OpenAIEmbedding, BgeEmbedding
from rag.vector_stores import ChromaVectorStore
from rag.custom_retriever import BilingualRetriever
from rag.prompts import PromptManager


class RAGAgent:
    def __init__(
            self,
            llm_name: str = "gpt-4o-mini",
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

        # Init scoped logger for RAGAgent
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.propagate = True

        try:
            self.response_template = response_template
            self.llm_name = llm_name
            if "gpt" in self.llm_name.lower():
                self.llm_type = "gpt"
            elif "claude" in self.llm_name.lower():
                self.llm_type = "claude"
            self.llm = self._init_llm()
            self.prompt_manager = PromptManager(self.llm_type)
            self.embedders = self._init_embeddings()
            self.vector_stores = self._init_vector_stores(vector_db_persist_dir)
        except Exception as e:
            self.logger.critical(f"RAGAgent initialization failed: {e}")
            raise
    
    def _init_llm(self):
        """
        Initializes an LLM instance based on the provided llm_name.

        Parameters:
            llm_name (str): The name of the LLM model to initialize.

        Returns:
            ChatOpenAI or ChatBedrock instance.

        Raises:
            RuntimeError: If initialization fails.
        """
        try:
            if "gpt" in self.llm_name.lower():
                llm = ChatOpenAI(
                    model=self.llm_name,
                    temperature=0
                )
                self.logger.info(f"LLM '{self.llm_name}' initialized successfully with ChatOpenAI.")
            elif "claude" in self.llm_name.lower():
                llm = ChatBedrock(
                    model_id=self.llm_name,
                    region_name="us-east-1",
                    model_kwargs=dict(temperature=0),
                    max_tokens=3000,
                )
                self.logger.info(f"LLM '{self.llm_name}' initialized successfully with ChatBedrock.")
            else:
                raise ValueError(f"Unsupported LLM name: '{self.llm_name}'")

            return llm
        except Exception as e:
            self.logger.critical(f"Failed to initialize LLM '{self.llm_name}': {e}")
            raise RuntimeError(f"Failed to initialize LLM: {e}")
        
    def _init_embeddings(self) -> dict:
        """
        Initialize embedding models and handle any errors during initialization.
        Embedding models to convert texts to embeddings (vectors)
        
        :return: Dictionary containing successfully initialized embedding models.
        """
        embedders = {}
        embedding_models = {
            "openai": OpenAIEmbedding,
            # "bge_en": lambda: BgeEmbedding("BAAI/bge-small-en-v1.5"),
            # "bge_zh": lambda: BgeEmbedding("BAAI/bge-small-zh-v1.5"),
            "bge_en": lambda: BgeEmbedding("BAAI/bge-base-en-v1.5"),
            "bge_zh": lambda: BgeEmbedding("BAAI/bge-base-zh-v1.5"),
            # "bge_en": lambda: BgeEmbedding("BAAI/bge-large-en-v1.5"),
            # "bge_zh": lambda: BgeEmbedding("BAAI/bge-large-zh-v1.5"),
        }

        for key, embedder_cls in embedding_models.items():
            try:
                embedders[key] = embedder_cls().model
                self.logger.info(f"Successfully initialized {key} embedding.")
            except Exception as e:
                self.logger.warning(f"Skipping {key} embedding due to error: {e}")

        if not embedders:
            self.logger.critical("Failed to initialize all embeddings. RAGAgent cannot proceed.")
            raise RuntimeError("No embeddings initialized.")

        return embedders
    
    def _init_vector_stores(self, persist_dir: Optional[str]) -> dict:
        """
        Initialize Chroma vector stores with a priority:
        1. Use "bge_en" and "bge_zh" if available.
        2. Fallback to "openai" for both "en" and "zh" if "bge" embeddings are unavailable.
        3. Raise an error if no suitable embeddings are available.

        :param persist_dir: Directory for persistent storage of vector databases.
        :return: A dictionary of ChromaVectorStore objects for English and Chinese.
        """
        vector_stores = {}
        try:
            embedder = self.embedders.get("bge_en") and self.embedders.get("bge_zh")
            if embedder:
                vector_stores["en"] = self._create_vector_store("docs_en", self.embedders["bge_en"], persist_dir)
                vector_stores["zh"] = self._create_vector_store("docs_zh", self.embedders["bge_zh"], persist_dir)
            elif self.embedders.get("openai"):
                vector_stores["en"] = self._create_vector_store("docs_en", self.embedders["openai"], persist_dir)
                vector_stores["zh"] = self._create_vector_store("docs_zh", self.embedders["openai"], persist_dir)
            else:
                raise RuntimeError("No suitable embeddings found for vector stores.")
        except Exception as e:
            self.logger.critical(f"Failed to initialize vector stores: {e}")
            raise

        return vector_stores
    
    def _create_vector_store(self, collection_name: str, embedding_model, persist_dir: str) -> ChromaVectorStore:
        try:
            return ChromaVectorStore(
                collection_name=collection_name,
                embedding_model=embedding_model,
                persist_directory=persist_dir,
            )
        except Exception as e:
            self.logger.error(f"Error creating vector store {collection_name}: {e}")
            raise

    
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
        search_kwargs = {
            "k": 5,
            "fetch_k": 20,
            "lambda_mult": 0.2,  # 0~1, smaller value, higher diversity
        }
        search_type = "mmr"
        english_retriever = self.vector_stores['en'].as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs
        )
        chinese_retriever = self.vector_stores['zh'].as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs
        )

        # Initialize the bilingual retriever with both English and Chinese retrievers
        bilingual_retriever = BilingualRetriever(english_retriever=english_retriever, 
                                                 chinese_retriever=chinese_retriever)
        
        context_query = self.prompt_manager.get_prompt("context_query")

        # Create the prompt template using LangChain's ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", context_query),
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

        :param retrieved_docs: List of text chunks retrieved from the vector store. will be injected into context in the promot.
        :return: An LCEL Runnable. The Runnable return is a dictionary containing at the very least a context and answer key.
        """

        template = self.response_template or self.prompt_manager.get_prompt("response_template")


        prompt = ChatPromptTemplate.from_messages([
            ("system", template),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"), # input = user query
        ])

        stuff_documents_chain = create_stuff_documents_chain(self.llm, prompt)
        retrieval_chain = create_retrieval_chain(retrieved_docs, stuff_documents_chain)
        return retrieval_chain
    
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
        # .pick() keeps only key="answer" in the response
        answer_only_retrieval_chain = retrieval_chain.pick("answer") 
        response = answer_only_retrieval_chain.stream({
            "chat_history": chat_history,
            "input": user_query
        })

        # return response["answer"] # use this if use retrieval_chain.invoke()
        return response


