# src/db_mysql/mysql_manager.py

from db_mysql.dao import Base, WebPage, WebPageChunk, FilePage, FilePageChunk
from sqlalchemy import create_engine, insert, select, delete, update, tuple_
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import hashlib
from datetime import datetime
import inspect

class MySQLManager:
    def __init__(self, host, user, password, port, db_name):
        """
        Initialize the SQLAlchemy engine and session.
        """

        self.db_uri = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}"

        # Check if the database exists, if not create it
        try:
            if not database_exists(self.db_uri):
                create_database(self.db_uri)
            self.engine = create_engine(self.db_uri, echo=True)  # engine = DB connector
            self.Session = sessionmaker(bind=self.engine)
            Base.metadata.create_all(self.engine) # Create tables if they do not exist
        except SQLAlchemyError as e:
            print(f"Error initializing database: {e}")

    def create_session(self):
        """Create a new session."""
        return self.Session()

    def close_session(self, session):
        """Close the session."""
        session.close()
    
    def close(self):
        """Close the database engine."""
        self.engine.dispose()
        print("Database connection closed.")

    def get_all_urls(self, session):
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
        
    
    def get_active_urls(self, session):
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
            

    def check_web_page_exists(self, session, url):
        """
        Check if a web page already exists in the database.
        if exists, return the first WebPage object.
        """
        cur_checksum = hashlib.sha256(url.encode('utf-8')).hexdigest()
        # Check if URL is already in the database
        # SELECT first row FROM WebPage WHERE checksum = cur_checksum
        sql_stmt = select(WebPage).filter_by(checksum=cur_checksum)
        existing_page = session.scalars(sql_stmt).first()
        if existing_page:
            return existing_page
        return None


    def insert_web_page(self, session, url, refresh_freq=None, language='en'):
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

    def insert_web_pages(self, session, document_info_list):
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
        
    def insert_web_page_chunks(self, session, chunk_info_list):
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
        

    def insert_file_pages(self, session, document_info_list):
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

        
    def insert_file_page_chunks(self, session, chunk_info_list):
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

    def update_web_pages_date(self, session, urls: list[str]):
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
    

    def update_single_web_page_date(self, session, url: str):
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


    def delete_web_pages_by_sources(self, session, sources: list[str]):
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

        except SQLAlchemyError as e:
            session.rollback()
            raise RuntimeError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error deleting WebPages: {e}")

    def delete_web_page_chunks_by_ids(self, session, chunk_ids):
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

        except SQLAlchemyError as e:
            session.rollback()  # Rollback in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error deleting chunks: {e}")

    def delete_file_pages_by_sources_and_pages(self, session, sources_and_pages: list[dict[str, str]]):
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
            session.commit()  # Commit the transaction to delete records

        except SQLAlchemyError as e:
            session.rollback()
            raise RuntimeError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error deleting FilePages: {e}")
        
    def delete_file_page_chunks_by_ids(self, session, chunk_ids):
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

        except SQLAlchemyError as e:
            session.rollback()  # Rollback in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error deleting chunks: {e}")

        
    def get_web_page_chunk_ids_by_single_source(self, session, source: str):
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
        
    def get_web_page_chunk_ids_by_sources(self, session, sources: list[str]):
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

    def get_file_page_chunk_ids(self, session, sources_and_pages: list[dict[str, str]]):
        """
        Get all chunk IDs for the given list of sources and pages.

        :param session: SQLAlchemy session to interact with the database.
        :param sources_and_pages: List of dictionaries where each dictionary contains a 'source' and 'page' to match.
                                Example: [{'source': 'example.com', 'page': '1'}, {'source': 'example.com', 'page': '2'}]
        :return: List of chunk IDs whose (source, page) pairs match the input list.
        """
        if not sources_and_pages:
            return []  # Early return if no sources or pages are provided

        try:
            # Build a list of tuples representing the source and page pairs
            source_page_pairs = [(item['source'], item['page']) for item in sources_and_pages]

            # Query all FilePageChunk objects that match any of the (source, page) pairs in the list
            sql_stmt = select(FilePageChunk.id).where(
                tuple_(FilePageChunk.source, FilePageChunk.page).in_(source_page_pairs)
            )
            chunk_ids = session.scalars(sql_stmt).all()
            return chunk_ids

        except SQLAlchemyError as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error fetching chunk IDs for sources and pages: {e}")
            return []
        
        
    def get_web_page_language_by_single_source(self, session, source: str):
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
    
    def get_web_page_languages_by_sources(self, session, sources: list[str]) -> dict[str, list[str]]:
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
        
    

