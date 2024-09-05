# src/db_mysql/mysql_manager.py

from db_mysql.dom import Base, WebPage, WebPageChunk
from sqlalchemy import create_engine, insert
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import hashlib
from datetime import datetime

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

    def check_web_page_exists(self, session, url):
        """
        Check if a web page already exists in the database.
        if exists, return the first WebPage object.
        """
        cur_checksum = hashlib.sha256(url.encode('utf-8')).hexdigest()
        # Check if URL is already in the database
        # SELECT first row FROM WebPage WHERE checksum = cur_checksum
        existing_page = session.query(WebPage).filter_by(checksum=cur_checksum).first()
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
            print(f"An error occurred: {e}")
            # raise  # Re-raise exception to handle it higher up if needed

    def insert_web_pages(self, session, document_info_list):
        """
        Insert multiple new web pages in batch.

        :param session: SQLAlchemy session to interact with the database.
        :param document_info_list: List[dict] [{'source': source, 'refresh_freq': freq}, {...}]
        :return: List[int] - List of IDs for the inserted web pages.
        """
        try:
            if not document_info_list:
                print("No valid data to insert.")
                return
            
            # Add the checksum to each entry
            for document in document_info_list:
                source = document.get('source')
                if source:
                    # Calculate and add the checksum
                    document['checksum'] = hashlib.sha256(source.encode('utf-8')).hexdigest()
                    # Add the current date for the web page
                    document['date'] = datetime.now()

            # Perform bulk insert using ORM's insert statement
            stmt = insert(WebPage)  # Create an insert statement for the WebPage ORM model
            result = session.execute(stmt, document_info_list)  # Execute the bulk insert

            # Extract the IDs of the inserted rows from the result
            # inserted_ids = [row['id'] for row in result.returned_defaults]
            # return inserted_ids

        except SQLAlchemyError as e:
            session.rollback()  # Rollback transaction in case of error
            print(f"An error occurred during bulk insert WebPage: {e}")

    def insert_web_page_chunks(self, session, document_info_list):
        """
        Insert chunks associated with a web page in batch.

        :param session: SQLAlchemy session to interact with the database.
        :param document_info_list: List[dict] [{'id': uuid4, 'source': source}, {...}]
        """
        try:
            if not document_info_list:
                print("No valid data to insert.")
                return
            
            # Perform bulk insert using ORM's insert statement and Session.execute()
            stmt = insert(WebPageChunk)  # ORM insert statement
            session.execute(stmt, document_info_list)
        except SQLAlchemyError as e:
            session.rollback()
            print(f"An error occurred during bulk insert WebPageChunk: {e}")

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
            urls = session.query(WebPage.source).all()
            # Extract URLs from the query result
            return {url[0] for url in urls}
        except SQLAlchemyError as e:
            print(f"An error occurred while fetching URLs: {e}")
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
            web_pages = session.query(WebPage).all()
            # Filter URLs that don't need a refresh: either None or Not due
            active_urls = {web_page.source for web_page in web_pages if not web_page.is_refresh_needed()}

            return active_urls
        
        except SQLAlchemyError as e:
            print(f"An error occurred while fetching active URLs: {e}")
            return set()

