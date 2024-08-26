# rag/agent.py
import os
from rag.parsers import PDFParser, ExcelParser
from rag.scrapers import WebScraper
from rag.embedders import OpenAIEmbedding, HuggingFaceBgeEmbedding
from rag.vectore_stores import ChromaVectorStore

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

class RAGAgent:
    def __init__(self, vector_db=None, retriever=None, response_template=None):
        """
        Initialize the RAGAgent with necessary components.
        
        :attr scraper: Web scraper utility for scraping contents from URLs
        :attr parser: File parser utility for parsing uploaded files
        :attr embedder: Embedding model to convert texts to embeddings (vectors)
        :param vector_store: Instance of a vector store (e.g., Chroma)
        :param retriever: Retriever utility to fetch relevant information from the vector store
        :param response_template: Predefined template for formatting responses
        """
        self.scraper = WebScraper()
        
        self._file_parsers = {}  # {'.pdf': PDFParser(), '.xls': ExcelParser(), '.xlsx': ExcelParser(), ...}
        
        # TODO: change embedder_type='openai' to 'bge' later when Chinese embedding is supported
        try:
            self.embedder = self._init_embedder(embedder_type='openai')
        except ValueError as e:
            print(f"Initialization Error for Embedding Model: {e}")
            self.embedder = None
        except Exception as e:
            print(f"Unexpected Error in getting Embedding Model: {e}")
            self.embedder = None

        self.vector_store = ChromaVectorStore(
            collection_name="subject_to_change",
            embedding_function=self.embedder,
            persist_db_name=vector_db,
        )


        self.retriever = retriever
        self.response_template = response_template
        

    def process_url(self, url):
        """
        Process a given URL: scrape content, embed, and save to vector store.
        
        :param url: The URL to scrape content from
        :return: None
        """
        # Step 1: Scrape content from the URL
        docs, downloaded_files = self.scraper.scrape(url)
        
        # Step 2: Split content into manageable chunks
        chunks = self.split_text(docs)
        
        # Step 3: Embed each chunk (Document) and save to the vector store
        chunk_ids = self.vector_store.add_documents(chunks)
        
        # Step 4: Save embeddings and chunks to the vector store
        # self.vector_store.save(embeddings, chunks)

        # Step 5: parse downloaded files

    def process_file(self, file):
        """
        Process an uploaded file: parse file content (i.e. conert to List[List[Document]])
        
        :param file: The uploaded file. Currently support: PDF, Excel (multiple sheets)
        :return: None
        """
        # Step 1: Select file parser based on the file extension, load and parse the file
        parser = self._select_parser(file)
        docs = parser.load_and_parse()

        # Step 2: Split content into manageable chunks
        chunks = self.split_text(docs)

        # Step 3: Embed each chunk (Document) and save to the vector store
        chunk_ids = self.vector_store.add_documents(chunks)
        
        # Step 4: Save embeddings and chunks to the vector store
        # self.vector_store.save(embeddings, chunks)

    def split_text(self, docs):
        """
        Split the docs (List[Document]) into smaller chunks suitable for embedding.
        
        :param docs: List[Document]
        :return: List[Document]
        """
        # Add additional separators customizing for Chinese texts
        # Ref: https://python.langchain.com/v0.1/docs/modules/data_connection/document_transformers/recursive_text_splitter/
        text_splitter = RecursiveCharacterTextSplitter(
            separators=[
                "\n\n",
                "\n",
                " ",
                ".",
                ",",
                "\u200b",  # Zero-width space
                "\uff0c",  # Fullwidth comma
                "\u3001",  # Ideographic comma
                "\uff0e",  # Fullwidth full stop
                "\u3002",  # Ideographic full stop
                "",
            ],
            # Existing args
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        doc_chunks = text_splitter.split_documents(docs)
        return doc_chunks
    

    def get_context_retriever_chain(self):
        """
        Set up and return the retriever chain using the initialized vector store, LLM, and a predefined prompt.
        
        :return: Retriever chain object
        """
        if not self.vector_store:
            raise ValueError("Vector store is not initialized. Cannot create retriever chain.")
        
        # TODO: define it as attribute or not????
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
        )
        
        retriever = self.vector_store.as_retriever()

        contextualize_q_system_prompt = (
            "Given a chat history and the latest user question "
            "which might reference context in the chat history, "
            "formulate a standalone question which can be understood "
            "without the chat history. Do NOT answer the question, "
            "just reformulate it if needed and otherwise return it as is."
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        retriever_chain = create_history_aware_retriever(llm, retriever, prompt)
        return retriever_chain
    
    def handle_query(self, query):
        """
        Handle a user query by retrieving relevant information and formatting a response.
        
        :param query: The user's query
        :return: Formatted response to the query
        """
        # Step 1: Retrieve relevant chunks from the vector store
        relevant_chunks = self.retriever.retrieve(query)
        
        # Step 2: Format the response using the predefined template
        response = self.format_response(relevant_chunks)
        
        return response

    def format_response(self, relevant_chunks):
        """
        Format the retrieved chunks into a coherent response based on a template.
        
        :param relevant_chunks: List of text chunks retrieved from the vector store
        :return: Formatted response string
        """
        # Implement your response formatting logic here using the response_template
        pass

    def _select_parser(self, file):
        """
        Determine the type of file and return the appropriate parser.
        Reuse the parser instance if it already exists.
        Return corresponding Parser object based on the file extension.
        """
        file_ext = os.path.splitext(file.name)[1].lower()

        if file_ext not in self._file_parsers:
            # Instantiate a new parser object if it doesn't exist in the dictionary
            if file_ext == '.pdf':
                self._file_parsers[file_ext] = PDFParser(file)
            elif file_ext in ['.xls', '.xlsx']:
                self._file_parsers[file_ext] = ExcelParser(file)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
        else:
            # Update the existing parser with the new file
            self._file_parsers[file_ext].file = file

        return self._file_parsers[file_ext]
    
    def _init_embedder(self, embedder_type):
        """
        Initialize the embedding model based on the provided type.
        
        :param embedder_type: <str> Type of embedding model to use ("openai" or "bge")
        :return: The model instance from the embedding model
        :raises ValueError: If the embedder type is not supported or if the API key is missing.
        """
        embedder_type = embedder_type.lower()

        if embedder_type == "openai":
            try:
                openai_embedding = OpenAIEmbedding()
                return openai_embedding.model 
            except ValueError as e:
                raise ValueError(f"Failed to initialize OpenAI Embeddings: {e}")
        elif embedder_type == "bge":
            try:
                huggingface_embedding = HuggingFaceBgeEmbedding()
                return huggingface_embedding.model
            except Exception as e:
                raise ValueError(f"Failed to initialize Hugging Face BGE Embeddings: {e}")
        else:
            raise ValueError(f"Unsupported embedder type: {embedder_type}")

