# src/rag/agent.py
import os
from typing import Optional, Literal, List, Tuple
from langchain.schema import Document
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from db_mysql import MySQLManager
from rag.parsers import PDFParser, ExcelParser
from rag.scrapers import WebScraper
from rag.embedders import OpenAIEmbedding, BgeEmbedding
from rag.vectore_stores import ChromaVectorStore
from rag.text_processor import TextProcessor
from rag.custom_retriever import BilingualRetriever


class RAGAgent:
    def __init__(
            self,
            mysql_config: dict, 
            vector_db: Optional[str] = None, 
            response_template: Optional[str] = None,
            llm: str = "gpt-4o-mini"
    ) -> None:
        """
        Initialize the RAGAgent with necessary components.
        
        :attr scraper: Web scraper utility for scraping contents from URLs
        :attr parser: File parser utility for parsing uploaded files
        :attr embedder: Embedding model to convert texts to embeddings (vectors)

        :param mysql_config: (dict) - MySQL configuration dictionary
        :param llm: (str) - Name of the language model (e.g., "gpt-4o-mini")
        :param vector_db: (str | None) - Name of Chroma's persistent directory. Used to constrcut persistent directory. If None, storage is in-memory and emphemeral.
        :param response_template: (str | None) - Predefined template for formatting responses
        :return: None
        """

        self.mysql_manager = MySQLManager(**mysql_config)

        self.scraper = WebScraper(mysql_manager=self.mysql_manager)
        
        # self._file_parsers = {}  # {'.pdf': PDFParser(), '.xls': ExcelParser(), '.xlsx': ExcelParser(), ...}

        self.text_processor = TextProcessor()

        if response_template:
            self.response_template = response_template
        else:
            self.response_template = """
                Your answer should be in the format of a report that follows the structure below: 
                <Title>: give a proper title
                <Summary>: key points that should be highlighted
                <Details>: provide details to each key point and enrich the details with numbers and statistics
                <Conclusion>: give a proper conclusion
                For any numbers or statistics you provide, please add the source in brackets.
                At the end of the report, please provide a list of references. 
                You should respond with the whole report in Chinese.
                """

            
        # TODO: modify the way to write it later
        self.llm = ChatOpenAI(
            model=llm,
            temperature=0,
        )
        
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
            collection_name="default",
            embedding_model=self.embedder,
            persist_db_name=vector_db,
        )


        # TODO: in progress
        self.embedders = {
            "openai": OpenAIEmbedding().model,
            "bge_en": BgeEmbedding(model_name="BAAI/bge-small-en-v1.5").model,
            "bge_zh": BgeEmbedding(model_name="BAAI/bge-small-zh-v1.5").model,
        }

        # TODO: in progress
        self.vector_stores = {
            "en": ChromaVectorStore(
                collection_name="docs_en",  # English collection
                embedding_model=self.embedders['bge_en'],
                persist_db_name=vector_db,
            ),
            "zh": ChromaVectorStore(
                collection_name="docs_zh",  # Chinese collection
                embedding_model=self.embedders['bge_zh'],
                persist_db_name=vector_db,
            ),
        }

    def process_file(self, filepath: str, language: Literal["en", "zh"] = "en"):
        """
        Process an uploaded file: parse file content, embed, and save to vector store.
        
        :param filepath: (str) The file path. Currently support: PDF (multiple pages), Excel (multiple sheets)
        :param language: The language of the web page content. Only "en" (English) or "zh" (Chinese) are accepted.
        :return: None
        """
        try:
            # Step 1: Check if the file already exists in the database
            if self._file_source_exists(filepath):
                print(f"File <{filepath}> already exists in the database.")
                return

            # Step 2: Parse the file based on the file extension
            docs, metadata = self._parse_file(filepath, language)

            # Step 3: Clean content before splitting
            self.text_processor.clean_page_content(docs)

            # Step 4: Split content into manageable chunks
            new_file_pages_chunks = self.text_processor.split_text(docs)

            # Step 5: Embed each chunk (Document) and save to the vector store
            chunk_metadata_list = self.insert_file_data(docs_metadata=metadata, chunks=new_file_pages_chunks, language=language)
            print(f"Data successfully inserted into both Chroma and MySQL: {len(chunk_metadata_list)} data chunks")

        except FileNotFoundError as e:
            print(f"File not found: {filepath}")
        except ValueError as e:
            print(f"Invalid file or language: {e}")
        except RuntimeError as e:
            print(f"Runtime error occurred: {e}")
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
        
        
    def process_url(self, url: str, max_pages: int = 1, autodownload: bool = False, refresh_frequency: Optional[int] = None, language: Literal["en", "zh"] = "en"):
        """
        Process a given URL: scrape content, embed, and save to vector store.
        
        :param url: start URL to scrape content from
        :param max_pages: The maximum number of pages to scrape. If > 1, scrape sub-URLs using BFS. Default is 1.
        :param autodownload: Whether to automatically download files linked in the URL. Default is False.
        :param refresh_frequency: The frequency in days to re-scrape and update the page content.
        :param language: The language of the web page content. Only "en" (English) or "zh" (Chinese) are accepted.
        :return: None
        """
        # Step 1: Scrape content from the URL
        web_pages, newly_downloaded_files = self.scraper.scrape(url, max_pages, autodownload)

        # Step 2: Categorize the web_pages into new, expired, and up-to-date
        # TODO: handle expired_docs, up_to_date_docs later
        new_web_pages, expired_web_pages, up_to_date_web_pages = self._categorize_web_documents(web_pages)

        if not new_web_pages:
            print("No new web pages scraped")
            return 0, 0

        # Step 3: Extract metadata for the new documents
        # new_web_pages_metadata := [{'source': source, 'refresh_frequency': freq, 'language': lang}]
        new_web_pages_metadata = self.extract_metadata(new_web_pages, refresh_frequency, language)

        # Step 4: Clean content before splitting
        self.text_processor.clean_page_content(new_web_pages)
        
        # Step 5: Split content into manageable chunks
        new_web_pages_chunks = self.text_processor.split_text(new_web_pages)


        # Step 6: Insert data: insert content into Chroma, insert metadata into MySQL
        # chunk_metadata_list := [{'source': source, 'id': chunk_id}, ...]
        try:
            chunk_metadata_list = self.insert_web_data(docs_metadata=new_web_pages_metadata, chunks=new_web_pages_chunks, language=language)
            print(f"Data successfully inserted into both Chroma and MySQL: {len(chunk_metadata_list)} data chunks")
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

        self.text_processor.clean_page_content(update_web_page)

        update_web_page_chunks = self.text_processor.split_text(update_web_page)

        try:
            chunk_metadata_list = self.update_web_data(source=url, chunks=update_web_page_chunks)
            print(f"Data successfully updated in both Chroma and MySQL: {chunk_metadata_list}")
        except RuntimeError as e:
            print(f"Failed to update data in Chroma and MySQL due to an error: {e}")

        # Reset self.scraped_urls in WebScraper instance
        self.scraper.fetch_active_urls_from_db()

    def _parse_file(self, filepath: str, language: Literal["en", "zh"] = "en") -> Tuple[List[Document], dict]:
        """
        Process an uploaded file: parse file content, embed, and save to vector store.
        
        :param filepath: (str) The file path. Currently supports: PDF (multiple pages), Excel (multiple sheets)
        :param language: The language of the web page content. Only "en" (English) or "zh" (Chinese) are accepted.
        :return: A tuple containing a list of Langchain Document objects and metadata.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"The file {filepath} does not exist.")
        
        file_ext = os.path.splitext(filepath)[1].lower()

        # Select the appropriate parser based on file extension
        if file_ext == '.pdf':
            parser_class = PDFParser
        elif file_ext in ['.xls', '.xlsx']:
            parser_class = ExcelParser
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        parser = parser_class(filepath)
        try:
            docs, metadata = parser.load_and_parse() # metadata := [{'source': src, 'page': page}]

            # Further processing of docs and metadata
            # Step 1: Augment metadata with language and ensure 'page' is a string
            for item in metadata:
                item["language"] = language
                item["page"] = str(item["page"])  # Convert page number to string
            
            # Step 2: Additional processing for Excel files
            if file_ext in ['.xls', '.xlsx']:
                for doc, meta in zip(docs, metadata):
                    # Replace doc.page_content with doc.metadata['text_as_html']
                    if 'text_as_html' in doc.metadata:
                        doc.page_content = doc.metadata['text_as_html']
                    # Add doc.metadata['page'] = metadata['page']
                    doc.metadata['page'] = meta['page']
                    # Replace doc.metadata['source'] with metadata['source'] as doc.metadata['source'] is .md
                    doc.metadata['source'] = meta['source']
            
            return docs, metadata
        
        except Exception as e:
            raise RuntimeError(f"Error parsing file {filepath}: {e}")

        
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
                huggingface_embedding = BgeEmbedding()
                return huggingface_embedding.model
            except Exception as e:
                raise ValueError(f"Failed to initialize Hugging Face BGE Embeddings: {e}")
        else:
            raise ValueError(f"Unsupported embedder type: {embedder_type}")
        

    def _categorize_web_documents(self, docs: List[Document]):
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
    
    def _file_source_exists(self, filepath: str) -> bool:
        """
        Check if the file already exists in the FilePage database based on the source filepath.

        :param filepath: The file path to check.
        :return: True if the file exists in the database, otherwise False.
        """
        # Extract the filename from the file path
        # filename = os.path.basename(filepath)

        # Query the database to see if the filename exists in the FilePage table
        session = self.mysql_manager.create_session()
        try:
            # Check if the file exists in the database
            existing_file = self.mysql_manager.check_file_exists_by_source(session, filepath)

            # Return True if the file exists, False otherwise
            return existing_file is not None
        except Exception as e:
            print(f"Error checking if file exists in the database: {e}")
            return False
        finally:
            self.mysql_manager.close_session(session)
    
    def extract_metadata(self, docs: List[Document], refresh_frequency: Optional[int] = None, language: Literal["en", "zh"] = "en", extra_metadata: Optional[dict] = None):
        """
        Extract metadata from the web page documents and optionally augment it with additional metadata.

        :param docs: List[Document]
        :param refresh_frequency: The re-scraping frequency in days for web contents. Keep None for uploaded files.
        :param language: The language of the web page/uploaded file content, either "en" (English) or "zh" (Chinese).
        :param extra_metadata: Optional dictionary to augment each dict with additional metadata.
        :return: List[dict] - [{'source': src, 'refresh_frequency': refresh_freq, 'language': lang}]
        """
        document_info_list = []
        
        for doc in docs:
            source = doc.metadata.get('source', None)
            if source:
                # Step 1: Create the base atom dictionary
                atom = {
                    'source': source, 
                    'refresh_frequency': refresh_frequency, 
                    'language': language
                }

                # Step 2: Merge additional metadata from the dictionary (if provided) into atom
                if extra_metadata:
                    atom.update(extra_metadata)
                
                document_info_list.append(atom)
            else:
                print(f"Source not found in metadata: {doc.metadata}")

        return document_info_list
    
    # def extract_web_metadata(self, docs, refresh_frequency: Optional[int] = None, language: Literal["en", "zh"] = "en"):
    #     """
    #     Extract metadata from the web page documents.

    #     :param docs: List[Document]
    #     :param refresh_frequency: The re-scraping frequency in days for web contents. Keep None for uploaded files.
    #     :param language: The language of the web page/uploaded file content, either "en" (English) or "zh" (Chinese)
    #     :return: List[dict] - [{'source': source, 'refresh_frequency': refresh_frequency, 'language': language}]
    #     """
    #     document_info_list = []
    #     for doc in docs:
    #         source = doc.metadata.get('source', None)
    #         if source:
    #             atom = {
    #                 'source': source, 
    #                 'refresh_frequency': refresh_frequency, 
    #                 'language': language
    #             }
                
    #             document_info_list.append(atom)
    #         else:
    #             print(f"Source not found in metadata: {doc.metadata}")

    #     return document_info_list
    
    # def extract_file_metadata(self, docs, docs_metadata, language: Literal["en", "zh"] = "en"):
    #     """
    #     Extract metadata from the documents parsed from uploaded files (pdf, excel).

    #     :param docs: List[Document]
    #     :param docs_metadata: List[dict] - Metadata of the documents generated along with docs. [{'source': source, 'page': page}]
    #     :param language: The language of the web page/uploaded file content, either "en" (English) or "zh" (Chinese)
    #     :return: List[dict]
    #     """
    #     document_info_list = []
    #     for doc in docs:
    #         source = doc.metadata.get('source', None)
    #         if source:
    #             atom = {'source': source, 'language': language}
    #             page = doc.metadata.get('page', None)
    #             if page:
    #                 atom['page'] = page
    #             document_info_list.append(atom)
    #         else:
    #             print(f"Source not found in metadata: {doc.metadata}")
        
    #     return document_info_list
    

    def insert_web_data(self, docs_metadata: List[dict], chunks: List[Document], language: Literal["en", "zh"]):
        """
        Wrapper function to handle atomic insertion of scraped web content into Chroma (for embeddings) and MySQL (for metadata).
        Implements the manual two-phase commit (2PC) pattern.
        
        :param docs_metadata: List[dict] - Metadata of documents to be inserted into MySQL.
        :param chunks: List[Document] - Chunks of document text to be inserted into Chroma.
        :param language: The language of the inserted data content. Only "en" (English) or "zh" (Chinese) are accepted.
        :raises: Exception if any part of the insertion process fails.
        :return: List[dict] chunks_metadata - Metadata of chunks inserted into Chroma.
        """
        session = self.mysql_manager.create_session()
        try:
            # Step 1: Insert embeddings into Chroma (vector store)
            chunks_metadata = self.vector_stores[language].add_documents(documents=chunks)

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
                    self.vector_stores[language].delete(ids=chunk_ids)  # Delete embeddings by ids in Chroma
                except Exception as chroma_rollback_error:
                    print(f"Failed to rollback Chroma insertions: {chroma_rollback_error}")

                raise RuntimeError(f"Data insertion failed: {e}")
        
        finally:
            self.mysql_manager.close_session(session)

    def insert_file_data(self, docs_metadata: List[dict], chunks: List[Document], language: Literal["en", "zh"]):
        """
        Wrapper function to handle atomic insertion of uploaded file content into Chroma (for embeddings) and MySQL (for metadata).
        Implements the manual two-phase commit (2PC) pattern.
        
        :param docs_metadata: List[dict] - Metadata of documents to be inserted into MySQL. {"source": filename, "page": page num/sheet name, "language": en/zh}
        :param chunks: List[Document] - Chunks of document text to be inserted into Chroma.
        :param language: The language of the inserted data content. Only "en" (English) or "zh" (Chinese) are accepted.
        :raises: Exception if any part of the insertion process fails.
        :return: List[dict] chunks_metadata - Metadata of chunks inserted into Chroma.
        """
        session = self.mysql_manager.create_session()
        try:
            # Step 1: Insert embeddings into Chroma (vector store)
            ## chunks_metadata := [{'id': uuid4, 'source': filename, 'page': page num/sheet name}]
            chunks_metadata = self.vector_stores[language].add_documents(documents=chunks, secondary_key='page')

            # Step 2: Insert metadata into MySQL
            self.mysql_manager.insert_file_pages(session, docs_metadata)
            self.mysql_manager.insert_file_page_chunks(session, chunks_metadata)

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
                    self.vector_stores[language].delete(ids=chunk_ids)  # Delete embeddings by ids in Chroma
                except Exception as chroma_rollback_error:
                    print(f"Failed to rollback Chroma insertions: {chroma_rollback_error}")

                raise RuntimeError(f"Data insertion failed: {e}")
        
        finally:
            self.mysql_manager.close_session(session)
        
    def update_web_data(self, source: str, chunks: List[Document]):
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
            old_chunk_ids = self.mysql_manager.get_web_page_chunk_ids_by_single_source(session, source)
            # 1-2: MySQL: Get language by source
            language = self.mysql_manager.get_web_page_language_by_single_source(session, source)
            # 1-3: Chroma: Get old documents from Chroma before deletion (for potential rollback)
            # TODO: old_documents = self.vector_store.get_documents_by_ids(ids=old_chunk_ids)
            old_documents = self.vector_stores[language].get_documents_by_ids(ids=old_chunk_ids)

            # Step 2: Delete
            # 2-1: MySQL: Delete WebPageChunk by old ids
            self.mysql_manager.delete_web_page_chunks_by_ids(session, old_chunk_ids)
            # 2-2: Chroma: Delete old chunks by old ids
            # TODO: self.vector_store.delete(ids=old_chunk_ids)
            self.vector_stores[language].delete(ids=old_chunk_ids)

            # Step 3: Upsert
            # 3-1: MySQL: Update the 'date' field for WebPage
            self.mysql_manager.update_web_pages_date(session, [source])
            # 3-2: Chroma: Insert new chunks into Chroma, get new chunk ids.
            # TODO: new_chunks_metadata = self.vector_store.add_documents(chunks)
            new_chunks_metadata = self.vector_stores[language].add_documents(chunks)
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
                    # TODO: self.vector_store.delete(new_chunk_ids)
                    self.vector_stores[language].delete(new_chunk_ids)

                # Restore old chunks to Chroma if they were deleted
                if old_documents:
                    # TODO: self.vector_store.add_documents(documents=old_documents, ids=old_chunk_ids)
                    self.vector_stores[language].add_documents(documents=old_documents, ids=old_chunk_ids)
            except Exception as chroma_rollback_error:
                print(f"Failed to rollback Chroma insertions: {chroma_rollback_error}")

            # Raise the error to indicate failure
            raise RuntimeError(f"Data update failed: {e}")
        finally:
            self.mysql_manager.close_session(session)

    def get_file_metadata(self, sources: Optional[list[str]] = None):
        """
        Get FilePage content (metadata) for uploaded files by their sources if provided; otherwise, return all on source level.
        
        :param sources: Optional list of sources of the uploaded file pages to be fetched. [{'source': str}]. If None, return all.
        :return: List[dict] - Metadata of the uploaded file pages stored in FilePage table.
        """
        session = self.mysql_manager.create_session()
        try:
            file_metadata = self.mysql_manager.get_files(session, sources)
            return file_metadata
        except Exception as e:
            print(f"Error getting file metadata: {e}")
            return []
        finally:
            self.mysql_manager.close_session(session)


    def get_file_page_metadata(self, sources_and_pages: Optional[list[dict]] = None):
        """
        Get FilePage content (metadata) for uploaded files by their sources and pages if provided; otherwise, return all on (source, page) level.
        
        :param sources_and_pages: Optional list of sources and pages of the uploaded file pages to be fetched. [{'source': str, 'page': str}]. If None, return all.
        :return: List[dict] - Metadata of the uploaded file pages stored in FilePage table.
        """
        session = self.mysql_manager.create_session()
        try:
            # Get metadata for uploaded files by sources and pages if provided; otherwise, return all
            file_metadata = self.mysql_manager.get_file_pages(session, sources_and_pages)
            return file_metadata
        except Exception as e:
            print(f"Error getting file metadata: {e}")
            return []
        finally:
            self.mysql_manager.close_session(session)


    def delete_web_data_by_sources(self, sources: list[str]):
        """
        Delete data for multiple sources by their language.
        
        :param sources: List of sources (e.g. URLs) of the web pages to be deleted.
        :return: None
        """
        # Get and categorize sources by language: {'en': [source1, source2], 'zh': [source3, source4]}
        sources_by_language = self.mysql_manager.get_web_page_languages_by_sources(sources)

        # Process deletion for English sources
        if sources_by_language['en']:
            self.delete_web_content_and_metadata(sources_by_language['en'], language="en")

        # Process deletion for Chinese sources
        if sources_by_language['zh']:
            self.delete_web_content_and_metadata(sources_by_language['zh'], language="zh")

    def delete_file_content_and_metadata(self, sources_and_pages: list[dict[str, str]], language: Literal["en", "zh"]):
        """
        Delete content data from Chroma and metadata from MySQL for a list of uploaded files.
        Implements atomic behavior using manual two-phase commit (2PC) pattern.
        
        :param sources_and_pages: List of sources and pages of the uploaded file pages to be deleted. [{'source': str, 'page': str}]
        :param language: The language of the web page content. Only "en" (English) or "zh" (Chinese) are accepted.
        :return: None
        :raises: RuntimeError if any part of the deletion process fails.
        """
        session = self.mysql_manager.create_session()
        try:
            # Step 1: Get
            # 1-1: MySQL: Get all chunk ids for the given sources and pages
            old_chunk_ids = self.mysql_manager.get_file_page_chunk_ids(session, sources_and_pages)
            # 1-2: Chroma: Get old documents from Chroma before deletion (for potential rollback)
            old_documents = self.vector_stores[language].get_documents_by_ids(ids=old_chunk_ids)

            # Step 2: Delete
            # 2-1: MySQL: Delete FilePageChunk by old chunk ids
            self.mysql_manager.delete_file_page_chunks_by_ids(session, old_chunk_ids)
            # 2-2: MySQL: Delete FilePage by sources and pages
            self.mysql_manager.delete_file_pages_by_sources_and_pages(session, sources_and_pages)
            # 2-3: Chroma: Delete chunks by old chunk ids
            self.vector_stores[language].delete(ids=old_chunk_ids)

            # Step 3: Commit MySQL transaction
            session.commit()

            print(f"Successfully deleted data for sources: {sources_and_pages}")
        
        except Exception as e:
            # Rollback MySQL transaction if any error occurs
            session.rollback()
            print(f"Error deleting data for sources {sources_and_pages}: {e}")
            
            # Rollback Chroma changes if MySQL fails
            try:
                # Restore old chunks to Chroma if they were deleted
                if old_documents:
                    self.vector_stores[language].add_documents(documents=old_documents, ids=old_chunk_ids, secondary_key='page')
            except Exception as chroma_rollback_error:
                print(f"Failed to rollback Chroma insertions: {chroma_rollback_error}")

            # Raise the error to indicate failure
            raise RuntimeError(f"Data deletion failed for sources {sources_and_pages}: {e}")
        finally:
            self.mysql_manager.close_session(session)
    
    def delete_web_content_and_metadata(self, sources: list[str], language: Literal["en", "zh"]):
        """
        Delete content data from Chroma and metadata from MySQL for a list of web sources.
        Implements atomic behavior using manual two-phase commit (2PC) pattern.
        
        :param sources: List of sources (e.g. URLs) of the web pages to be deleted.
        :param language: The language of the web page content. Only "en" (English) or "zh" (Chinese) are accepted.
        :return: None
        :raises: RuntimeError if any part of the deletion process fails.
        """
        session = self.mysql_manager.create_session()
        try:
            # Step 1: Get
            # 1-1: MySQL: Get all chunk ids for the given sources
            old_chunk_ids = self.mysql_manager.get_web_page_chunk_ids_by_sources(session, sources)
            # 1-2: Chroma: Get old documents from Chroma before deletion (for potential rollback)
            old_documents = self.vector_stores[language].get_documents_by_ids(ids=old_chunk_ids)

            # Step 2: Delete
            # 2-1: MySQL: Delete WebPageChunk by old chunk ids
            self.mysql_manager.delete_web_page_chunks_by_ids(session, old_chunk_ids)
            # 2-2: MySQL: Delete WebPages by sources
            self.mysql_manager.delete_web_pages_by_sources(session, sources)
            # 2-3: Chroma: Delete chunks by old chunk ids
            self.vector_stores[language].delete(ids=old_chunk_ids)

            # Step 3: Commit MySQL transaction
            session.commit()

            print(f"Successfully deleted data for sources: {sources}")

        except Exception as e:
            # Rollback MySQL transaction if any error occurs
            session.rollback()
            print(f"Error deleting data for sources {sources}: {e}")
            
            # Rollback Chroma changes if MySQL fails
            try:
                # Restore old chunks to Chroma if they were deleted
                if old_documents:
                    self.vector_stores[language].add_documents(documents=old_documents, ids=old_chunk_ids)
            except Exception as chroma_rollback_error:
                print(f"Failed to rollback Chroma insertions: {chroma_rollback_error}")

            # Raise the error to indicate failure
            raise RuntimeError(f"Data deletion failed for sources {sources}: {e}")
        finally:
            self.mysql_manager.close_session(session)
    

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
        # TODO: relevant_chunks = self._retrieve_contextual_docs()
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
    
    def _retrieve_contextual_docs(self):
        """
        Retrieve relevant documents from the vector store based on the chat history and the user's query.
        1. This function first looks at the chat history and the current user's question.
        2. It then uses the LLM to reformulate the question if necessary. e.g., user query "Please explain green hydrogen to me" might be transformed to "What is green hydrogen and how does it relate to renewable energy sources?" This reformulation takes into account the previous conversation about renewable energy sources.
        3. The reformulated question is then used to retrieve relevant documents from the vector store. In our example, it retrieved three key pieces of information about green hydrogen.

        :return: Runnable[Any, List[Document]] - An LCEL Runnable. The Runnable output is a list of Documents. For simple understanding, returned is a list of relevant documents retrieved from the vector store
        """
        if not self.vector_store:
            raise ValueError("Vector store is not initialized. Cannot create retriever chain.")
        
        vector_store_retriever = self.vector_store.as_retriever()

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

        retrieved_docs = create_history_aware_retriever(self.llm, vector_store_retriever, prompt)
        return retrieved_docs
    
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
            ("system", "Combine the given chat history and the following pieces of retrieved context to answer the user's question.\n{context}"), # context = retrieved_docs
            ("system", self.response_template),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"), # input = user query
        ])
        stuff_documents_chain = create_stuff_documents_chain(self.llm, prompt)
        retrieval_chain = create_retrieval_chain(retrieved_docs, stuff_documents_chain)
        return retrieval_chain


