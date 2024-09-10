# src/db_mysql/mysql_manager.py

from db_mysql.dom import Base, WebPage, WebPageChunk
from sqlalchemy import create_engine, insert, select, delete
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
            self.engine = create_engine(self.db_uri)  # engine = DB connector
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

    def insert_web_page_metadata(self, session, web_pages_metadata, web_page_chunks_metadata):
        """
        Insert web pages and their associated chunks in one operation.

        :param session: SQLAlchemy session to interact with the database.
        :param web_pages_metadata: List[dict] [{'source': source, 'refresh_freq': freq}, {...}] - Metadata for web pages.
        :param web_page_chunks_metadata: List[dict] [{'id': uuid4, 'source': source}, {...}] - Metadata for the associated chunks.
        :raises: Exception if insertion fails.
        :return: None
        """
        try:
            if not web_pages_metadata or not web_page_chunks_metadata:
                raise ValueError("No valid data to insert into MySQL.")
            
            # Insert web pages
            self.insert_web_pages(session, web_pages_metadata)

            # Insert web page chunks
            self.insert_web_page_chunks(session, web_page_chunks_metadata)

        except SQLAlchemyError as e:
            session.rollback()  # Rollback the transaction in case of error
            raise RuntimeError(f"Error inserting WebPages and WebPageChunks: {e}")
            


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


    def insert_web_page(self, session, url, refresh_freq=None):
        """
        Insert a new web page if it does not exist.
        """
        try:
            new_page = WebPage(source=url, freq=refresh_freq)
            session.add(new_page)
            session.commit()  # Commit transaction here
        except SQLAlchemyError as e:
            session.rollback()  # Rollback transaction in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error insert WebPage: {e}")
            # raise  # Re-raise exception to handle it higher up if needed

    def insert_web_pages(self, session, document_info_list):
        """
        Insert multiple new web pages in batch.

        :param session: SQLAlchemy session to interact with the database.
        :param document_info_list: List[dict] [{'source': source, 'refresh_freq': freq}, {...}]
        :return: List[int] - List of IDs for the inserted web pages.
        """
        try:
            # Add the checksum to each entry
            for document in document_info_list:
                source = document.get('source')
                if source:
                    # Calculate and add the checksum
                    document['checksum'] = hashlib.sha256(source.encode('utf-8')).hexdigest()
                    # Add the current date for the web page
                    document['date'] = datetime.now()

            # Perform bulk insert using ORM's insert statement
            sql_stmt = insert(WebPage)  # Create an insert statement for the WebPage ORM model
            _ = session.execute(sql_stmt, document_info_list)  # Execute the bulk insert. Return Result object.

            # Extract the IDs of the inserted rows from the result
            # inserted_ids = [row['id'] for row in result.returned_defaults]
            # return inserted_ids

        except SQLAlchemyError as e:
            session.rollback()  # Rollback transaction in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error batch insert WebPage: {e}")

    def insert_web_page_chunks(self, session, document_info_list):
        """
        Insert chunks associated with a web page in batch.

        :param session: SQLAlchemy session to interact with the database.
        :param document_info_list: List[dict] [{'id': uuid4, 'source': source}, {...}]
        """
        try:            
            # Perform bulk insert using ORM's insert statement and Session.execute()
            sql_stmt = insert(WebPageChunk)  # ORM insert statement
            session.execute(sql_stmt, document_info_list)
        except SQLAlchemyError as e:
            session.rollback()
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error batch insert WebPageChunk: {e}")

    def delete_web_page_chunks(self, session, chunk_ids):
        """
        Delete web page chunks that match the given list of chunk IDs.

        :param session: SQLAlchemy session to interact with the database.
        :param chunk_ids: List of chunk IDs to delete.
        :return: None
        """
        if not chunk_ids:
            print("No chunk IDs provided for deletion.")
            return

        try:
            # Create a delete statement with a filter for the chunk IDs
            sql_stmt = delete(WebPageChunk).where(WebPageChunk.id.in_(chunk_ids))

            # Execute the statement
            session.execute(sql_stmt)

            # Commit the transaction to finalize the deletion
            session.commit()

        except SQLAlchemyError as e:
            session.rollback()  # Rollback in case of error
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error deleting chunks: {e}")

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
        
    def get_chunk_ids_by_source(self, session, source):
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

