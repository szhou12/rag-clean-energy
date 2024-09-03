# src/db_mysql/mysql_manager.py

from db_mysql.dom import Base, WebPage, WebPageChunk
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import hashlib

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
        existing_page = session.query(WebPage).filter_by(checksum=cur_checksum).first()
        if existing_page:
            return existing_page
        return None


    def insert_web_page(self, session, url, refresh_freq=None):
        """Insert a new web page if it does not exist."""
        checksum = hashlib.sha256(url.encode('utf-8')).hexdigest()

        try:
            existing_page = session.query(WebPage).filter_by(checksum=checksum).first()
            if existing_page:
                return existing_page.id  # Return existing web page ID

            new_page = WebPage(source=url, freq=refresh_freq)
            session.add(new_page)
            session.commit()  # Commit transaction here
            return new_page.id

        except SQLAlchemyError as e:
            session.rollback()  # Rollback transaction in case of error
            print(f"An error occurred: {e}")
            # raise  # Re-raise exception to handle it higher up if needed

    def insert_web_page_chunks(self, session, checksum, chunk_ids):
        """Insert chunks associated with a web page."""
        for chunk_id in chunk_ids:
            new_chunk = WebPageChunk(chunk_id=chunk_id, source_checksum=checksum)
            session.add(new_chunk)
        session.commit()

    def close(self):
        """Close the database engine."""
        self.engine.dispose()
        print("SQLAlchemy engine disposed.")

