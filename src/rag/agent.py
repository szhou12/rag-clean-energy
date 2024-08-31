# rag/agent.py
import os
import re
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
    def __init__(self, llm="gpt-4o-mini", embedder='openai', vector_db=None, response_template=None):
        """
        Initialize the RAGAgent with necessary components.
        
        :attr scraper: Web scraper utility for scraping contents from URLs
        :attr parser: File parser utility for parsing uploaded files
        :attr embedder: Embedding model to convert texts to embeddings (vectors)

        :param llm: <str> Name of the language model (e.g., "gpt-4o-mini")
        :param embedder: <str> Name of embedding model
        :param vector_db: <str> Name of a vector store (e.g., Chroma). Used to constrcut persistent directory
        :param response_template: Predefined template for formatting responses
        """
        self.scraper = WebScraper()
        
        self._file_parsers = {}  # {'.pdf': PDFParser(), '.xls': ExcelParser(), '.xlsx': ExcelParser(), ...}
        
        # TODO: change embedder_type='openai' to 'bge' later when Chinese embedding is supported
        try:
            self.embedder = self._init_embedder(embedder_type=embedder)
        except ValueError as e:
            print(f"Initialization Error for Embedding Model: {e}")
            self.embedder = None
        except Exception as e:
            print(f"Unexpected Error in getting Embedding Model: {e}")
            self.embedder = None

        self.vector_store = ChromaVectorStore(
            collection_name="default",
            embedding_model=self.embedder,
            persist_db_name=vector_db,
        )

        # TODO: modify the way to write it later
        self.llm = ChatOpenAI(
            model=llm,
            temperature=0,
        )

        if response_template:
            self.response_template = response_template
        else:
            self.response_template = """
                Your answer should be in the format of a report that follows the structure: 
                <Title>: give a proper title
                <Summary>: key points that should be highlighted
                <Details>: provide details to each key point and enrich the details with numbers and statistics
                <Conclusion>: give a proper conclusion
                """
        

    def process_url(self, url, max_pages=1, autodownload=False):
        """
        Process a given URL: scrape content, embed, and save to vector store.
        
        :param url: The URL to scrape content from
        :return: None
        """
        # Step 1: Scrape content from the URL
        docs, newly_downloaded_files = self.scraper.scrape(url, max_pages, autodownload)

        # Step 2: Clean content before splitting
        # clean up \n and whitespaces to obtain compact text
        self.clean_page_content(docs)
        
        # Step 3: Split content into manageable chunks
        chunks = self.split_text(docs)
        
        # Step 4: Embed each chunk (Document) and save to the vector store
        chunk_ids = self.vector_store.add_documents(chunks)
        
        # Step 4: Save embeddings and chunks to the vector store
        # self.vector_store.save(embeddings, chunks)

        # Step 5: parse downloaded files

        return len(docs), len(newly_downloaded_files)

    def process_file(self, file):
        """
        Process an uploaded file: parse file content, embed, and save to vector store.
        
        :param file: The uploaded file. Currently support: PDF, Excel (multiple sheets)
        :return: None
        """
        # Step 1: Select file parser based on the file extension, load and parse the file
        parser = self._select_parser(file)
        docs = parser.load_and_parse()

        # Step 2: Clean content before splitting
        self.clean_page_content(docs)

        # Step 3: Split content into manageable chunks
        chunks = self.split_text(docs)

        # Step 4: Embed each chunk (Document) and save to the vector store
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
    
    def handle_query(self, user_query, chat_history):
        """
        Handle a user query by retrieving relevant information and formatting a contextual response by referring to the chat history.
        Workflow:
            user query -> _retrieve_contextual_info() retrieve relevant docs -> _format_response() format response
        
        :param query: The user's query
        :param chat_history: The chat history
        :return: Formatted response to the query
        """
        # Step 1: Retrieve relevant chunks from the vector store
        relevant_chunks = self._retrieve_contextual_info()
        
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
    
    def _retrieve_contextual_info(self):
        """
        Retrieve relevant information from the vector store based on the chat history and the user's query.
        1. This function first looks at the chat history and the current user's question.
        2. It then uses the LLM to reformulate the question if necessary. e.g., user query "Please explain green hydrogen to me" might be transformed to "What is green hydrogen and how does it relate to renewable energy sources?" This reformulation takes into account the previous conversation about renewable energy sources.
        3. The reformulated question is then used to retrieve relevant documents from the vector store. In our example, it retrieved three key pieces of information about green hydrogen.

        :return: Runnable[Any, List[Document]] - An LCEL Runnable. The Runnable output is a list of Documents. For simple understanding, returned is a list of relevant documents retrieved from the vector store
        """
        if not self.vector_store:
            raise ValueError("Vector store is not initialized. Cannot create retriever chain.")
        
        vs_retriever = self.vector_store.as_retriever()

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

        retrieved_docs = create_history_aware_retriever(self.llm, vs_retriever, prompt)
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
            ("system", "Combine the given chat history and the following pieces of retrieved context to answer the user's question.\n\n{context}"), # context = retrieved_docs
            ("system", self.response_template),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"), # input = user query
        ])
        stuff_documents_chain = create_stuff_documents_chain(self.llm, prompt)
        retrieval_chain = create_retrieval_chain(retrieved_docs, stuff_documents_chain)
        return retrieval_chain

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
        
    def clean_page_content(self, docs):
        """
        Clean up the page content of each document in the list.
        Change happens in-place.

        :param docs: List[Document]
        """
        for document in docs:
            cleaned_content = self._clean_text(document.page_content)
            document.page_content = cleaned_content
    
    def _clean_text(self, text: str) -> str:
        """
        Clean up text:
        1. handle newline characters '\n'
        2. handle whitespaces
        3. other situations

        :param text: The input text to clean.
        :return: The cleaned text with repeated newlines removed.
        """
        # Remove UTF-8 BOM if present. its presence can cause issues in text processing
        text = text.replace('\ufeff', '')

        # Replace multiple newlines with a single newline, preserving paragraph structure
        text = re.sub(r'\n{2,}', '\n\n', text)

        # Replace all sequences of whitespace characters (spaces, tabs, etc.) excluding newline with a single space
        text = re.sub(r'[^\S\n]+', ' ', text)

        # Finally, strip leading and trailing whitespace (including newlines)
        return text.strip()

