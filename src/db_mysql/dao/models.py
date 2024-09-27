# src/db_mysql/dao/models.py

from typing import Optional, Literal
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import relationship, declarative_base
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
    source = Column(String(255), nullable=False, index=True)
    checksum = Column(String(64), unique=True, nullable=False) # SHA-256 checksum
    date = Column(DateTime, nullable=False)
    refresh_frequency = Column(Integer, nullable=True)  # Refresh frequency in days
    language = Column(String(10), nullable=False, default='en')  # New column for language, default is 'en'
    
    # Define relationship with/Create a link to WebPageChunk
    chunks = relationship("WebPageChunk", back_populates="web_page")

    def __init__(self, source: str, freq: Optional[int] = None, language: Literal["en", "zh"] = "en"):
        """
        Initialize a WebPage instance.
        
        :param source: URL of the web page.
        :param freq: Frequency in days for refreshing the page. Default is None (no automatic refresh).
        :param language: The language of the web page content (e.g., 'en', 'zh'). Default is 'en'.
        """
        self.source = source
        self.refresh_frequency = freq
        self.language = language
        self.checksum = hashlib.sha256(source.encode('utf-8')).hexdigest()
        self.date = datetime.now()  # Set the current date as the last scraped date

    def __repr__(self):
        return f'<WebPage(id={self.id}, url={self.source}, date={self.date}, refresh_frequency={self.refresh_frequency}, language={self.language})>'
    
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

    # Chunk id = UUID4 = 128-bit = 32 hex digits (4-bit) + 4 hyphens
    id = Column(String(36), primary_key=True)

    # Source = URL of the web page
    # NOTE: The foreign key ensures that one WebPageChunk maps to exactly one WebPage.
    source = Column(String(255), ForeignKey('web_page.source'), nullable=False)

    # Define relationship with/Create a link back to WebPage
    web_page = relationship("WebPage", back_populates="chunks")

    def __init__(self, id: str, source: str):
        self.id = id
        self.source = source

    def __repr__(self):
        return f'<WebPageChunk(chunk_id={self.id}, source_url={self.source})>'
    
    
class FilePage(Base):
    __tablename__ = 'file_page'
    id = Column(Integer, primary_key=True)
    source = Column(String(255), nullable=False, index=True) # Source file name
    page = Column(String(255), nullable=False) # PDF page number or Excel sheet name
    date = Column(DateTime, nullable=False, default=datetime.now) # The date when the file page was parsed
    language = Column(String(10), nullable=False, default='en') # Language of the content

    # Define relationship with/Create a link to FilePageChunk
    chunks = relationship("FilePageChunk", back_populates="file_page")

    def __init__(self, source: str, page: str, language: Literal["en", "zh"] = "en"):
        """
        Initialize a FilePage instance.
        
        :param source: File name of the uploaded file.
        :param page: PDF page number or Excel sheet name.
        :param language: The language of the file content (e.g., 'en', 'zh'). Default is 'en'.
        """
        self.source = source
        self.page = page
        self.language = language
        self.date = datetime.now()

    def __repr__(self):
        return f'<FilePage(id={self.id}, source={self.source}, page={self.page}, language={self.language})>'
    
    def days_since_added(self):
        """
        Calculate how many days it has been since the file page was added to the database.

        :return: Number of days since the file page was added
        """
        current_time = datetime.now()
        time_difference = current_time - self.date
        return time_difference.days

    def exist_in_db_over(self, days: int = 7):
        """
        Check if the file page has been in the database for more than a certain number of days.

        :param days: The number of days to check
        :return: True if the file page has been in the database for more than 'days', otherwise False
        """
        return self.days_since_added() > days
    
class FilePageChunk(Base):
    __tablename__ = 'file_page_chunk'

    id = Column(String(36), primary_key=True)
    
    # Composite foreign key referencing both source and page from FilePage
    source = Column(String(255), nullable=False)
    page = Column(String(255), nullable=False)

    # Define foreign key constraint on (source, page)
    __table_args__ = (
        ForeignKeyConstraint(['source', 'page'], ['file_page.source', 'file_page.page']),
    )

    # Relationship back to the parent FilePage
    file_page = relationship("FilePage", back_populates="chunks")

    def __init__(self, id: str, source: str, page: str):
        self.id = id
        self.source = source
        self.page = page

    def __repr__(self):
        return f'<FilePageChunk(id={self.id}, source={self.source}, page={self.page})>'