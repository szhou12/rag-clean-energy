# src/mysql/dom/models.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import hashlib

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
    
    # Define relationship with/Create a link to WebPageChunk
    chunks = relationship("WebPageChunk", back_populates="web_page")

    def __init__(self, source: str):
        self.source = source
        self.checksum = hashlib.sha256(source.encode('utf-8')).hexdigest()

    def __repr__(self):
        return f'<WebPage(id={self.id}, url={self.source}, date={self.date})>'
    
class WebPageChunk(Base):
    __tablename__ = 'web_page_chunk'

    chunk_id = Column(String(36), primary_key=True) # UUID
    # NOTE: The foreign key ensures that each WebPageChunk is associated with exactly one WebPage.
    source_checksum = Column(String(64), ForeignKey('web_page.checksum'), nullable=False)

    # Define relationship with/Create a link back to WebPage
    web_page = relationship("WebPage", back_populates="chunks")

    def __init__(self, chunk_id, checksum):
        self.chunk_id = chunk_id
        self.source_checksum = checksum

    def __repr__(self):
        return f'<WebPageChunk(chunk_id={self.chunk_id}, source_checksum={self.source_checksum})>'