# src/mysql/mysql_manager.py

from mysql.dom import Base, WebPage, WebPageChunk
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import hashlib

class MySQLManager:
    def __init__(self, host, user, password, database):
        """
        Initialize the SQLAlchemy engine and session.
        """
        self.engine = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}/{database}") # db_uri
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine) # Create tables if they do not exist

    def create_session(self):
        """Create a new session."""
        return self.Session()

    def close_session(self, session):
        """Close the session."""
        session.close()

    def insert_web_page(self, session, url):
        """Insert a new web page if it does not exist."""
        checksum = hashlib.sha256(url.encode('utf-8')).hexdigest()

        existing_page = session.query(WebPage).filter_by(checksum=checksum).first()
        if existing_page:
            return existing_page.id  # Return existing web page ID

        new_page = WebPage(source=url) # TODO: Add refresh frequency
        session.add(new_page)
        session.commit()
        return new_page.id

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


