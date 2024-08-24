# rag/agent.py
import os
from rag.parsers import PDFParser, ExcelParser
from rag.scrapers import WebScraper
from rag.embedders import OpenAIEmbedding, HuggingFaceBgeEmbedding

from langchain.text_splitter import RecursiveCharacterTextSplitter

class RAGAgent:
    def __init__(self, vector_store, retriever=None, response_template=None):
        """
        Initialize the RAGAgent with necessary components.
        
        :param scraper: Web scraper utility for scraping contents from URLs
        :param parser: File parser utility for parsing uploaded files
        :param embedder: Embedding model to convert texts to embeddings (vectors)
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

        self.vector_store = vector_store
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
        
        # Step 3: Embed the chunks
        embeddings = self.embedder.embed(chunks)
        
        # Step 4: Save embeddings and chunks to the vector store
        self.vector_store.save(embeddings, chunks)

        # Step 5: parse downloaded files

    def process_file(self, file):
        """
        Process an uploaded file: parse file content (i.e. conert to List[List[Document]])
        
        :param file: The uploaded file. Currently support: PDF, Excel (multiple sheets)
        :return: None
        """
        parser = self._select_parser(file)
        docs = parser.load_and_parse()

        
        ## Considering moving step 2-4 to separate methods
        # Step 2: Split content into manageable chunks
        # chunks = self.split_text(content)
        
        # Step 3: Embed the chunks
        # embeddings = self.embedder.embed(chunks)
        
        # Step 4: Save embeddings and chunks to the vector store
        # self.vector_store.save(embeddings, chunks)

    def split_text(self, docs):
        """
        Split the each List[Document] in docs into smaller chunks suitable for embedding.
        
        :param docs: [ List[Document], List[Document], ...]
        :return: [ List[Document], List[Document], ...]
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
        doc_chunks_list = [text_splitter.split_documents(doc) for doc in docs]
        return doc_chunks_list

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
