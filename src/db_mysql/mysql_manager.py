# src/db_mysql/mysql_manager.py
import hashlib
import inspect
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, insert, select, delete, update, tuple_, func, case
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from db_mysql.dao import Base, WebPage, WebPageChunk, FilePage, FilePageChunk

class MySQLManager:
    def __init__(
            self, 
            host: str, 
            port: int, 
            user: str, 
            password: str, 
            db_name: str,
    ):
        """
        Initialize the SQLAlchemy engine and session.
        Interact with MySQL running in a Docker container.

        NOTE:
        1. All CRUD operations in MySQLManager are not deemed as atomic operations (i.e. they are part of a larger transaction in DataAgent). Therefore, no commit is made in CRUD here.

        :param host: Host where MySQL is running.
        :param port: Port on which MySQL is running (default is 3306).
        :param user: MySQL username.
        :param password: MySQL password.
        :param db_name: Name of the MySQL database.
        """

        self.db_uri = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}"

        # Check if the database exists, if not create it
        try:
            if not database_exists(self.db_uri):
                create_database(self.db_uri)
            self.engine = create_engine(self.db_uri)  # self.engine := DB connector
            logging.info(f"Database engine created: {self.db_uri}")

            self.Session = sessionmaker(bind=self.engine) # <-- Create the session factory here
            Base.metadata.create_all(self.engine) # Create tables if they do not exist
            logging.info("Session factory and tables initialized.")
            
        except SQLAlchemyError as e:
            logging.error(f"Error initializing database: {e}")
            raise

    def create_session(self):
        """Create a new session."""
        return self.Session()

    def close_session(self, session: Session):
        """Close the session."""
        session.close()
    
    def close(self):
        """Close the database engine."""
        self.engine.dispose()
        print("MySQL Database connection closed.")


    ###########################
    ### Web Data Operations ###
    ###########################
    def get_all_urls(self, session: Session) -> set:
        """
        Get all URLs currently stored in the WebPage table.

        :param session: SQLAlchemy session to interact with the database.
        :return: Set of all URLs (source) stored in the web_page table.
        """
        try:
            # Query all URLs from the WebPage table using the provided session
            sql_stmt = select(WebPage.source)
            urls = session.scalars(sql_stmt).all()
            # Extract URLs from the query result
            return set(urls)
        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching URLs: {e}")
            return set()
        
    
    def get_active_urls(self, session: Session) -> set:
        """
        Get URLs that either do not require refresh (refresh_frequency = None) or
        are not due for refresh based on the last scraped date and refresh frequency.

        :param session: SQLAlchemy session to interact with the database.
        :return: Set of active URLs (source) that do not need to be refreshed.
        """
        try:
            # Query all WebPage objects from the database
            sql_stmt = select(WebPage)
            web_pages = session.scalars(sql_stmt).all()
            # Filter URLs that don't need a refresh: either None or Not due
            active_urls = {web_page.source for web_page in web_pages if not web_page.is_refresh_needed()}

            return active_urls
        
        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching active URLs: {e}")
            return set()
            

    def check_web_page_exists(self, session: Session, url: str):
        """
        Check if a web page already exists in the database.
        if exists, return the first WebPage object.
        """
        cur_checksum = hashlib.sha256(url.encode('utf-8')).hexdigest()
        # Check if URL is already in the database
        # SELECT first row FROM WebPage WHERE checksum = cur_checksum
        sql_stmt = select(WebPage).where(WebPage.checksum == cur_checksum)
        existing_page = session.scalars(sql_stmt).first()
        return existing_page
    
    def insert_web_page(self, session: Session, url: str, refresh_freq: int = None, language: str = 'en'):
        """
        Insert a new web page if it does not exist, with a specified language.

        :param session: SQLAlchemy session to interact with the database.
        :param url: URL of the web page.
        :param refresh_freq: Refresh frequency in days for the web page. Default is None.
        :param language: The language of the web page content (e.g., 'en', 'zh'). Default is 'en'.
        """
        try:
            new_page = WebPage(source=url, freq=refresh_freq, language=language)
            session.add(new_page)
            session.commit()  # Commit transaction here
        except SQLAlchemyError as e:
            session.rollback()  # Rollback transaction in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error insert WebPage: {e}")

    def insert_web_pages(self, session: Session, document_info_list: list[dict]):
        """
        Insert multiple new web pages in batch.

        :param session: SQLAlchemy session to interact with the database.
        :param document_info_list: List[dict] [{'source': url, 'refresh_frequency': freq, 'language': lang}]
        """
        try:
            # Add url checksum, current date, and language to each entry
            for document in document_info_list:
                source = document.get('source')
                if source:
                    # Calculate and add the checksum
                    document['checksum'] = hashlib.sha256(source.encode('utf-8')).hexdigest()
                    # Add the current date for the web page
                    document['date'] = datetime.now()

            # Perform bulk insert using ORM's insert statement
            sql_stmt = insert(WebPage)  # Create an insert statement for the WebPage ORM model
            session.execute(sql_stmt, document_info_list)  # Execute the bulk insert

        except SQLAlchemyError as e:
            session.rollback()  # Rollback transaction in case of error
            raise RuntimeError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error batch insert WebPage: {e}")
        
    def insert_web_page_chunks(self, session: Session, chunk_info_list: list[dict]):
        """
        Insert chunks associated with a web page in batch.

        :param session: SQLAlchemy session to interact with the database.
        :param chunk_info_list: List[dict] [{'id': uuid4, 'source': url}]
        """
        try:            
            # Perform bulk insert using ORM's insert statement and Session.execute()
            sql_stmt = insert(WebPageChunk)  # ORM insert statement
            session.execute(sql_stmt, chunk_info_list)
        except SQLAlchemyError as e:
            session.rollback()
            raise RuntimeError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error batch insert WebPageChunk: {e}")
        
    def update_web_pages_refresh_frequency(self, session: Session, sources_and_freqs: list[dict]):
        """
        Update the 'refresh_frequency' field of the WebPage objects corresponding to the given URLs.

        :param session: SQLAlchemy session to interact with the database.
        :param sources_and_freqs: List of dictionaries containing 'source' and 'refresh_frequency'.
                                Example: [{'source': 'https://rmi.org', 'refresh_frequency': 7},
                                          {'source': 'https://iea.org', 'refresh_frequency': 30}]
        """
        try:
            if not sources_and_freqs:
                print("No sources provided for updating.")
                return
            # Build a dictionary mapping each source to its new refresh frequency
            source_freq_map = {item['source']: item['refresh_frequency'] for item in sources_and_freqs if item.get('source') and item.get('refresh_frequency') is not None}
            
            # Construct a CASE statement to apply different values for each source
            case_stmt = case(source_freq_map, value=WebPage.source)
            
            # Perform a bulk update
            session.execute(
                update(WebPage).
                where(WebPage.source.in_(source_freq_map.keys())).
                values(refresh_frequency=case_stmt)
            )

            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Bulk updated 'refresh_frequency' for {len(sources_and_freqs)} WebPages.")

        except SQLAlchemyError as e:
            session.rollback()  # Rollback the transaction in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error updating WebPage refresh frequencies: {e}")
            raise RuntimeError(f"Failed to update WebPage refresh frequencies: {e}")
            
        
        

    def update_web_pages_date(self, session: Session, urls: list[str]):
        """
        Update the 'date' field of the WebPage objects corresponding to the given URLs.
        Resets the date to the current date.

        :param session: SQLAlchemy session to interact with the database.
        :param urls: List of URLs (strings) whose 'date' fields need to be reset.
        """
        try:
            if not urls:
                print("No URLs provided for updating.")
                return
            
            # Update the 'date' field for all URLs in the list
            sql_stmt = (
                update(WebPage)
                .where(WebPage.source.in_(urls))
                .values(date=datetime.now())
            )
            session.execute(sql_stmt)
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Updated 'date' for {len(urls)} WebPages.")

        except SQLAlchemyError as e:
            session.rollback()  # Rollback the transaction in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error updating WebPage dates: {e}")
            raise RuntimeError(f"Failed to update WebPage dates: {e}")
    

    def update_single_web_page_date(self, session: Session, url: str):
        """
        Update the 'date' field of the WebPage object corresponding to the given URL.
        Resets the date to the current date.

        :param session: SQLAlchemy session to interact with the database.
        :param url: A single URL (string) whose 'date' field needs to be reset.
        """
        try:
            if not url:
                print("No URL provided for updating.")
                return
            
            # Update the 'date' field for the specific URL
            sql_stmt = (
                update(WebPage)
                .where(WebPage.source == url)
                .values(date=datetime.now())
            )
            session.execute(sql_stmt)

            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Updated 'date' for WebPage with URL: {url}")

        except SQLAlchemyError as e:
            session.rollback()  # Rollback the transaction in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error updating WebPage date for URL: {e}")
            raise RuntimeError(f"Failed to update WebPage date for URL: {e}")


    def delete_web_pages_by_sources(self, session: Session, sources: list[str]):
        """
        Delete web pages that match the given list of source URLs.

        :param session: SQLAlchemy session to interact with the database.
        :param sources: List of source URLs to delete.
        :return: None
        :raises: RuntimeError if the deletion fails.
        """
        if not sources:
            print("No sources provided for deletion.")
            return

        try:
            # Create a delete statement with a filter for the provided sources
            sql_stmt = delete(WebPage).where(WebPage.source.in_(sources))
            session.execute(sql_stmt)
            # NOTE: No commit here as this transaction is part of a larger transaction in DataAgent

        except SQLAlchemyError as e:
            session.rollback()
            raise RuntimeError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error deleting WebPages: {e}")

    def delete_web_page_chunks_by_ids(self, session: Session, chunk_ids: list[str]):
        """
        Delete web page chunks that match the given list of chunk IDs.

        :param session: SQLAlchemy session to interact with the database.
        :param chunk_ids: List of chunk IDs (UUID4) to delete.
        :return: None
        """
        if not chunk_ids:
            print("No chunk IDs provided for deletion.")
            return

        try:
            # Create a delete statement with a filter for the chunk IDs
            sql_stmt = delete(WebPageChunk).where(WebPageChunk.id.in_(chunk_ids))
            session.execute(sql_stmt)
            # NOTE: No commit here as this transaction is part of a larger transaction in DataAgent

        except SQLAlchemyError as e:
            session.rollback()  # Rollback in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error deleting chunks: {e}")

        
    def get_web_page_chunk_ids_by_single_source(self, session: Session, source: str) -> list[str]:
        """
        Get all chunk IDs for the given the source.

        :param session: SQLAlchemy session to interact with the database.
        :param source: The source URL to match.
        :return: List of chunk IDs whose source matches the input.
        """
        try:
            # Query all WebPageChunk objects that match the source URL
            sql_stmt = select(WebPageChunk.id).filter_by(source=source)
            chunk_ids = session.scalars(sql_stmt).all()
            return chunk_ids
        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching chunk IDs for {source}: {e}")
            return []
        
    def get_web_page_chunk_ids_by_sources(self, session: Session, sources: list[str]) -> list[str]:
        """
        Get all chunk IDs for the given list of sources.

        :param session: SQLAlchemy session to interact with the database.
        :param sources: List of source URLs to match.
        :return: List of chunk IDs whose sources match the input list.
        """
        if not sources:
            return []  # Early return if no sources are provided

        try:
            # Query all WebPageChunk objects that match any of the source URLs in the list
            sql_stmt = select(WebPageChunk.id).where(WebPageChunk.source.in_(sources))
            chunk_ids = session.scalars(sql_stmt).all()
            return chunk_ids
        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching chunk IDs for batch sources {sources}: {e}")
            return []
    

    def get_web_page_language_by_single_source(self, session: Session, source: str) -> str:
        """
        Get the language of the web page for the given source.

        :param session: SQLAlchemy session to interact with the database.
        :param source: The source URL to match.
        :return: The language of the web page if found, otherwise None.
        """
        try:
            # Query the language field for the source URL
            sql_stmt = select(WebPage.language).filter_by(source=source)
            language = session.scalars(sql_stmt).first()
            return language
        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching language for {source}: {e}")
            return None
    
    def get_web_page_languages_by_sources(self, session: Session, sources: list[str]) -> dict[str, list[str]]:
        """
        Get the languages of the web pages for the given list of sources and group them by 'en' and 'zh'.

        :param session: SQLAlchemy session to interact with the database.
        :param sources: List of source URLs to match.
        :return: A dictionary with two keys 'en' and 'zh', where the values are lists of source URLs. {'en': [source 1, source 2, ...], 'zh': [source 1, ...]}
        """
        if not sources:
            return {'en': [], 'zh': []}
        
        try:
            # Query the WebPage objects that match any of the source URLs
            sql_stmt = select(WebPage.source, WebPage.language).where(WebPage.source.in_(sources))
            results = session.execute(sql_stmt).all()

            # Initialize the dictionary with two keys 'en' and 'zh'
            languages_dict = {'en': [], 'zh': []}

            # Group sources based on their language
            for source, language in results:
                if language in languages_dict:
                    languages_dict[language].append(source)

            return languages_dict

        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching languages for sources: {e}")
            return {'en': [], 'zh': []}
    
    def get_web_pages(self, session: Session, sources: Optional[list[str]] = None) -> list[dict]:
        """
        Get web pages from the WebPage table either by sources if provided,
        or fetch all rows if no sources are provided.

        :param session: SQLAlchemy session.
        :param sources: Optional list of sources (URLs) to filter by.
                        Example: ['https://iea.org/building', 'https://iea.org']
        :return: List of dictionaries, where each dictionary represents a WebPage object,
                 excluding 'checksum'.
                 Example: [{'id': 1, 'source': 'https://example.com', 'date': '2024-10-08', 
                            'language': 'en', 'refresh_frequency': 30}, ...]
        """
        try:
            # Case 1: No sources provided, fetch all web pages
            if sources is None:
                sql_stmt = select(WebPage)
            # Case 2: Sources provided, filter by 'source' field
            else:
                if not sources:
                    return []  # Early return if the list of sources is empty
                
                sql_stmt = select(WebPage).where(WebPage.source.in_(sources))

            # Execute the query and fetch matching WebPage objects
            web_pages = session.scalars(sql_stmt).all()

            # Convert each WebPage object into a dictionary
            result = [
                {
                    'id': page.id,
                    'source': page.source,
                    'date': page.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'language': page.language,
                    'refresh_frequency': page.refresh_frequency
                }
                for page in web_pages
            ]
            return result
        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.get_web_pages] Error fetching web pages: {e}")
            return []

    

    ############################
    ### File Data Operations ###
    ############################
    def check_file_exists_by_source(self, session: Session, file_source: str):
        """
        Check if a file source already exists in the database.
        if exists, return the first FilePage object.
        NOTE: coerce checking - it checks only source, assuming if source exists, then all pages exist.
        """
        sql_stmt = select(FilePage).where(FilePage.source == file_source)
        existing_file = session.scalars(sql_stmt).first()
        return existing_file
    
    def insert_file_pages(self, session: Session, document_info_list: list[dict]):
        """
        Insert multiple new file pages in batch.

        :param session: SQLAlchemy session to interact with the database.
        :param document_info_list: List[dict] [{'source': filename, 'page': page number/sheet name, 'language': lang}]
        """
        try:
            for document in document_info_list:
                source = document.get('source')
                if source:
                    # Add the current date for the web page
                    document['date'] = datetime.now()

            # Perform bulk insert using ORM's insert statement
            sql_stmt = insert(FilePage)
            session.execute(sql_stmt, document_info_list)
        except SQLAlchemyError as e:
            session.rollback()
            raise RuntimeError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error batch insert FilePage: {e}")

        
    def insert_file_page_chunks(self, session: Session, chunk_info_list: list[dict]):
        """
        Insert chunks associated with a file page in batch.

        :param session: SQLAlchemy session to interact with the database.
        :param chunk_info_list: List[dict] [{'id': uuid4, 'source': filename, 'page': page number/sheet name}]
        """
        try:
            # Perform bulk insert using ORM's insert statement and Session.execute()
            sql_stmt = insert(FilePageChunk)
            session.execute(sql_stmt, chunk_info_list)
        except SQLAlchemyError as e:
            session.rollback()
            raise RuntimeError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error batch insert FilePageChunk: {e}")
        
    def delete_file_pages_by_sources_and_pages(self, session: Session, sources_and_pages: list[dict[str, str]]):
        """
        Delete file pages that match the given list of (source, page) pairs.

        :param session: SQLAlchemy session to interact with the database.
        :param sources_and_pages: List of dictionaries, each containing 'source' and 'page'.
                                Example: [{'source': 'example.pdf', 'page': '1'}, {'source': 'example.xlsx', 'page': 'Sheet1'}]
        :return: None
        :raises: RuntimeError if the deletion fails.
        """
        if not sources_and_pages:
            print("No source-page pairs provided for deletion.")
            return

        try:
            # Build a list of tuples representing the (source, page) pairs
            source_page_pairs = [(item['source'], item['page']) for item in sources_and_pages]

            # Create a delete statement with a filter for the provided (source, page) pairs
            sql_stmt = delete(FilePage).where(
                tuple_(FilePage.source, FilePage.page).in_(source_page_pairs)
            )
            session.execute(sql_stmt)
            # NOTE: No commit here as this transaction is part of a larger transaction in DataAgent
        except SQLAlchemyError as e:
            session.rollback()
            raise RuntimeError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error deleting FilePages: {e}")
        
    def delete_file_page_chunks_by_ids(self, session: Session, chunk_ids: list[dict]):
        """
        Delete file page chunks that match the given list of chunk IDs.

        :param session: SQLAlchemy session to interact with the database.
        :param chunk_ids: List of chunk IDs (UUID4) to delete.
        :return: None
        """
        if not chunk_ids:
            print("No chunk IDs provided for deletion.")
            return

        try:
            # Create a delete statement with a filter for the chunk IDs
            sql_stmt = delete(FilePageChunk).where(FilePageChunk.id.in_(chunk_ids))
            session.execute(sql_stmt)
            # NOTE: No commit here as this transaction is part of a larger transaction in DataAgent

        except SQLAlchemyError as e:
            session.rollback()  # Rollback in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error deleting chunks: {e}")
    
    def get_files(self, session: Session, sources: Optional[list[dict]] = None) -> list[dict]:
        """
        Get unique sources from the FilePage table, excluding the 'page' field,
        and count the total number of pages/sheets for each unique source.

        :param session: SQLAlchemy session.
        :param sources: Optional list of dictionaries to filter by 'source'.
                        Example: [{'source': 'one.pdf'}, {'source': 'two.pdf'}, ...]
        :return: List of dictionaries containing unique sources with all fields except 'page',
                along with a count of how many records exist for each source.
                Example: [{'source': 'one.pdf', 'date': '2024-10-08', 'language': 'en', 'total_records': 3}, ...]
        """
        try:
             # Create a subquery to get the first record (earliest date) for each source
            subquery = (
                select(
                    FilePage.source,
                    FilePage.date,
                    FilePage.language,
                    func.row_number().over(partition_by=FilePage.source, order_by=FilePage.date).label('rn')
                )
                .subquery()
            )

            # Main query to get the unique sources and count the total number of records per source
            sql_stmt = (
                select(
                    subquery.c.source,
                    subquery.c.date,
                    subquery.c.language,
                    func.count(FilePage.source).label('total_records')
                )
                .select_from(subquery)
                .join(FilePage, FilePage.source == subquery.c.source)
                .where(subquery.c.rn == 1)
                .group_by(subquery.c.source, subquery.c.date, subquery.c.language)
            )

            # Filter by provided sources if not empty list
            if sources is not None and sources:
                source_list = [item['source'] for item in sources]
                sql_stmt = sql_stmt.where(FilePage.source.in_(source_list))

            # Execute the query and fetch the results
            unique_sources = session.execute(sql_stmt).all()

            # Convert results into a list of dictionaries
            result = [
                {
                    'source': source.source,
                    'date': source.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'language': source.language,
                    'total_records': source.total_records
                }
                for source in unique_sources
            ]

            return result

        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching unique sources: {e}")
            return []

        
    def get_file_pages(self, session: Session, metadata: Optional[list[dict]] = None) -> list[dict]:
        """
        Get documents from FilePage table either by ('source', 'page') pairs if metadata is provided,
        or fetch all rows if metadata is None. Unique at ('source', 'page') level.

        :param session: SQLAlchemy session.
        :param metadata: Optional list of document metadata dictionaries, containing at least a 'source' and 'page' to match.
                        Example: [{'source': 'path/to/one.pdf', 'page': '1', ...}, {'source': 'path/to/one.pdf', 'page': '2', ...}]
        :return: List of dictionaries, where each dictionary represents a FilePage object in the database.
                Example: [{'id': 1, 'source': 'path/to/file.pdf', 'page': '1', 'date': '2024-10-08', 'language': 'en'}, ...]
        """
        try:
            # Case 1: No metadata provided, fetch all file pages
            if metadata is None:
                sql_stmt = select(FilePage)
            # Case 2: Metadata provided, filter by ('source', 'page') pairs
            else:
                if not metadata:
                    return []  # Early return if no sources or pages are provided. e.g., empty list
                
                source_page_pairs = [(item['source'], item['page']) for item in metadata]
                sql_stmt = select(FilePage).where(
                    tuple_(FilePage.source, FilePage.page).in_(source_page_pairs)
                )

            # Execute query and fetch matching FilePage objects
            existing_docs = session.scalars(sql_stmt).all()

            # Convert each FilePage object into a dictionary
            result = [
                {
                    'id': doc.id,
                    'source': doc.source,
                    'page': doc.page,
                    'date': doc.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'language': doc.language
                }
                for doc in existing_docs
            ]

            return result

        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching file pages for sources and pages: {e}")
            return []


    def get_file_page_chunk_ids(self, session: Session, metadata: list[dict]):
        """
        Get all chunk IDs for the given list of sources and pages.

        :param session: SQLAlchemy session to interact with the database.
        :param metadata: List of dictionaries where each dictionary contains at least a 'source' and 'page' to match.
                                Example: [{'source': 'path/to/one.pdf', 'page': '1', ...}, {'source': 'path/to/one.pdf', 'page': '2', ...}]
        :return: List of chunk IDs whose (source, page) pairs match the input list.
        """
        if not metadata:
            return []  # Early return if no sources or pages are provided

        try:
            # Build a list of tuples representing the source and page pairs
            source_page_pairs = [(item['source'], item['page']) for item in metadata]

            # Query all FilePageChunk objects that match any of the (source, page) pairs in the list
            sql_stmt = select(FilePageChunk.id).where(
                tuple_(FilePageChunk.source, FilePageChunk.page).in_(source_page_pairs)
            )
            chunk_ids = session.scalars(sql_stmt).all()
            return chunk_ids

        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching chunk IDs for sources and pages: {e}")
            return []
    

