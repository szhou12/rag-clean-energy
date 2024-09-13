# src/rag/agent.py
import os
import re
from typing import Optional
from rag.parsers import PDFParser, ExcelParser
from rag.scrapers import WebScraper
from rag.embedders import OpenAIEmbedding, HuggingFaceBgeEmbedding
from rag.vectore_stores import ChromaVectorStore
from db_mysql import MySQLManager

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

class RAGAgent:
    def __init__(self, mysql_config, llm="gpt-4o-mini", embedder='openai', vector_db=None, response_template=None):
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

        self.mysql_manager = MySQLManager(**mysql_config)

        self.scraper = WebScraper(mysql_manager=self.mysql_manager)
        
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
                Your answer should cite sources for any numbers or statistics you provide.
                """
        

    def process_url(self, url: str, max_pages: int = 1, autodownload: bool = False, refresh_frequency: Optional[int] = None):
        """
        Process a given URL: scrape content, embed, and save to vector store.
        
        :param url: start URL to scrape content from
        :param max_pages: The maximum number of pages to scrape. If > 1, scrape sub-URLs using BFS. Default is 1.
        :param autodownload: Whether to automatically download files linked in the URL. Default is False.
        :param refresh_frequency: The frequency in days to re-scrape and update the page content
        :return: None
        """
        # Step 1: Scrape content from the URL
        web_pages, newly_downloaded_files = self.scraper.scrape(url, max_pages, autodownload)

        # Step 2: Categorize the web_pages into new, expired, and up-to-date
        # TODO: handle expired_docs, up_to_date_docs later
        new_web_pages, expired_web_pages, up_to_date_web_pages = self._categorize_documents(web_pages)

        # Step 3: Extract metadata for the new documents
        # new_web_pages_metadata = [{'source': source, 'refresh_frequency': freq}, ...]
        new_web_pages_metadata = self.extract_metadata(new_web_pages, refresh_frequency)

        # Step 4: Clean content before splitting
        # clean up \n and whitespaces to obtain compact text
        self.clean_page_content(new_web_pages)
        
        # Step 5: Split content into manageable chunks
        new_web_pages_chunks = self.split_text(new_web_pages)

        # Step 6: Insert data: insert content into Chroma, insert metadata into MySQL
        # chunk_metadata_list = [{'source': source, 'id': chunk_id}, ...]
        try:
            chunk_metadata_list = self.insert_data(docs_metadata=new_web_pages_metadata, chunks=new_web_pages_chunks)
            print(f"Data successfully inserted into both Chroma and MySQL: {chunk_metadata_list}")
        except RuntimeError as e:
            print(f"Failed to insert data into Chroma and MySQL due to an error: {e}")

        # Reset self.scraped_urls in WebScraper instance
        self.scraper.fetch_active_urls_from_db()

        return len(web_pages), len(newly_downloaded_files)
    
    def update_single_url(self, url: str):
        """
        Update the content of a given URL by re-scraping and re-embedding the content.

        :param url: The URL to update content for.
        """
        update_web_page = self.scraper.load_url(url)
        
        if update_web_page is None:
            print(f"Failed to load URL: {url}")
            return

        self.clean_page_content(update_web_page)

        update_web_page_chunks = self.split_text(update_web_page)

        try:
            chunk_metadata_list = self.update_data(source=url, chunks=update_web_page_chunks)
            print(f"Data successfully updated in both Chroma and MySQL: {chunk_metadata_list}")
        except RuntimeError as e:
            print(f"Failed to update data in Chroma and MySQL due to an error: {e}")

        # Reset self.scraped_urls in WebScraper instance
        self.scraper.fetch_active_urls_from_db()
        

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
    

    def _categorize_documents(self, docs):
        """
        Categorize documents (scraped web page) into new, expired, and up-to-date based on their status in the MySQL database.
        
        :param docs: List[Document] - Documents returned from the scraper.
        :return: Tuple[List[Document], List[Document], List[Document]] - (new_docs, expired_docs, up_to_date_docs)
        """
        new_docs = []
        expired_docs = []
        up_to_date_docs = []
        
        # Start a MySQL session
        session = self.mysql_manager.create_session()

        try:
            for document in docs:
                existing_page = self.mysql_manager.check_web_page_exists(session, document.metadata['source'])

                if existing_page:
                    if existing_page.is_refresh_needed():
                        expired_docs.append(document)
                    else:
                        up_to_date_docs.append(document)
                else:
                    new_docs.append(document)
        except Exception as e:
            print(f"An error occurred while categorizing documents: {e}")
        finally:
            # Close the session
            self.mysql_manager.close_session(session)

        return new_docs, expired_docs, up_to_date_docs
    
    def extract_metadata(self, docs, refresh_frequency: Optional[int] = None):
        """
        Extract metadata from the documents.

        :param docs: List[Document]
        :param refresh_frequency: The re-scraping frequency in days for web contents
        :return: List[dict] - [{'source': source, 'refresh_frequency': refresh_frequency}, {...}]
        """
        document_info_list = []
        for doc in docs:
            source = doc.metadata.get('source', None)
            if source:
                document_info_list.append({'source': source, 'refresh_frequency': refresh_frequency})
            else:
                print(f"Source not found in metadata: {doc.metadata}")

        return document_info_list
    

    def insert_data(self, docs_metadata, chunks):
        """
        Wrapper function to handle atomic insertion into Chroma (for embeddings) and MySQL (for metadata).
        Implements the manual two-phase commit (2PC) pattern.
        
        :param docs_metadata: List[dict] - Metadata of documents to be inserted into MySQL.
        :param chunks: List[Document] - Chunks of document text to be inserted into Chroma.
        :raises: Exception if any part of the insertion process fails.
        :return: List[dict] chunks_metadata - Metadata of chunks inserted into Chroma.
        """
        session = self.mysql_manager.create_session()
        try:
            # Step 1: Insert embeddings into Chroma (vector store)
            chunks_metadata = self.vector_store.add_documents(documents=chunks)  # Embedding vectors to Chroma

            # Step 2: Insert metadata into MySQL
            self.mysql_manager.insert_web_pages(session, docs_metadata)
            self.mysql_manager.insert_web_page_chunks(session, chunks_metadata)

            # Step 3: Commit MySQL transaction
            session.commit()

            # If both steps succeed, return the chunk metadata
            return chunks_metadata

        except Exception as e:
            # Rollback MySQL transaction if any error occurs
            session.rollback()
            print(f"Error during data insertion into Chroma and MySQL: {e}")

            # Rollback Chroma changes if MySQL fails
            if 'chunks_metadata' in locals():
                try:
                    chunk_ids = [item['id'] for item in chunks_metadata]
                    self.vector_store.delete(ids=chunk_ids)  # Delete embeddings by ids in Chroma
                except Exception as chroma_rollback_error:
                    print(f"Failed to rollback Chroma insertions: {chroma_rollback_error}")

                raise RuntimeError(f"Data insertion failed: {e}")
        
        finally:
            self.mysql_manager.close_session(session)
        
    def update_data(self, source, chunks):
        """
        Update data for a SINGLE source URL and its chunks.
        Implements atomic behavior using manual two-phase commit (2PC) pattern.
        
        :param source: Single URL of the web page being updated.
        :param chunks: List[Document] - New chunks of document text to be inserted into Chroma.
        :raises: RuntimeError if any part of the update process fails.
        :return: List[dict] new_chunks_metadata - Metadata of new chunks inserted into Chroma.
        """
        session = self.mysql_manager.create_session()
        try:
            # Step 1: Get
            # 1-1: MySQL: Get old chunk ids by source
            old_chunk_ids = self.mysql_manager.get_chunk_ids_by_single_source(session, source)
            # 1-2: Chroma: Get old documents from Chroma before deletion (for potential rollback)
            old_documents = self.vector_store.get_documents_by_ids(ids=old_chunk_ids)

            # Step 2: Delete
            # 2-1: MySQL: Delete WebPageChunk by old ids
            self.mysql_manager.delete_web_page_chunks_by_ids(session, old_chunk_ids)
            # 2-2: Chroma: Delete old chunks by old ids
            self.vector_store.delete(ids=old_chunk_ids)

            # Step 3: Upsert
            # 3-1: MySQL: Update the 'date' field for WebPage
            self.mysql_manager.update_web_pages_date(session, [source])
            # 3-2: Chroma: Insert new chunks into Chroma, get new chunk ids.
            new_chunks_metadata = self.vector_store.add_documents(chunks)
            # 3-3: MySQL: Insert new WebPageChunk into MySQL
            self.mysql_manager.insert_web_page_chunks(session, new_chunks_metadata)

            # Step 4: Commit MySQL transaction
            session.commit()

            # If all steps succeed, return the chunk metadata
            return new_chunks_metadata
            
        except Exception as e:
            # Rollback MySQL transaction if any error occurs
            session.rollback()
            print(f"Error updating data: {e}")
            
            # Rollback Chroma changes if MySQL fails
            try:
                # If we already inserted new chunks into Chroma, we need to delete them to maintain consistency
                if 'new_chunks_metadata' in locals():
                    new_chunk_ids = [item['id'] for item in new_chunks_metadata]
                    self.vector_store.delete(new_chunk_ids)

                # Restore old chunks to Chroma if they were deleted
                if old_documents:
                    self.vector_store.add_documents(documents=old_documents, ids=old_chunk_ids)
            except Exception as chroma_rollback_error:
                print(f"Failed to rollback Chroma insertions: {chroma_rollback_error}")

            # Raise the error to indicate failure
            raise RuntimeError(f"Data update failed: {e}")
        finally:
            self.mysql_manager.close_session(session)


