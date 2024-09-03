# src/db_mysql/dom/models.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import hashlib
from datetime import datetime, timedelta

# SQLAlchemy Base
Base = declarative_base()

# Define ORM Models
# WebPage --one-to-many--> WebPageChunk
# ForeignKey and relationship() enforces one-to-many
# 1. WebPage uses relationship() to indicate that it can have multiple WebPageChunk objects.
# 2. WebPageChunk uses ForeignKey to indicate that it is associated with a single WebPage.
class WebPage(Base):
    __tablename__ = 'web_page'
    id = Column(Integer, primary_key=True)
    source = Column(String(255), nullable=False)
    checksum = Column(String(64), unique=True, nullable=False) # SHA-256 checksum
    date = Column(DateTime, nullable=False)
    refresh_frequency = Column(Integer, nullable=True)  # Refresh frequency in days
    
    # Define relationship with/Create a link to WebPageChunk
    chunks = relationship("WebPageChunk", back_populates="web_page")

    def __init__(self, source: str, freq: int = None):
        """
        Initialize a WebPage instance.
        
        :param source: URL of the web page.
        :param freq: Frequency in days for refreshing the page. Default is None (no automatic refresh).
        """
        self.source = source
        self.checksum = hashlib.sha256(source.encode('utf-8')).hexdigest()
        self.date = datetime.now()  # Set the current date as the last scraped date
        self.refresh_frequency = freq

    def __repr__(self):
        return f'<WebPage(id={self.id}, url={self.source}, date={self.date}, refresh_frequency={self.refresh_frequency})>'
    
    def next_refresh_due(self):
        """
        Calculate the next refresh due date based on the refresh frequency.
        
        :return: The next refresh date or None if no refresh is set.
        """
        if self.refresh_frequency is None:
            return None
        return self.date + timedelta(days=self.refresh_frequency)

    def is_refresh_needed(self):
        """
        Check if the web page needs to be refreshed.
        
        :return: True if a refresh is needed, False otherwise.
        """
        if self.refresh_frequency is None:
            return False
        next_due_date = self.next_refresh_due()
        return datetime.now() >= next_due_date
    
class WebPageChunk(Base):
    __tablename__ = 'web_page_chunk'

    chunk_id = Column(String(36), primary_key=True) # UUID4 = 128-bit = 32 hex digits (4-bit) + 4 hyphens
    # NOTE: The foreign key ensures that one WebPageChunk maps to exactly one WebPage.
    source = Column(String(255), ForeignKey('web_page.source'), nullable=False)

    # Define relationship with/Create a link back to WebPage
    web_page = relationship("WebPage", back_populates="chunks")

    def __init__(self, chunk_id, source):
        self.chunk_id = chunk_id
        self.source = source

    def __repr__(self):
        return f'<WebPageChunk(chunk_id={self.chunk_id}, source={self.source})>'