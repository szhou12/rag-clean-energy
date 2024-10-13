# project/src/rag/__init__.py

from .agent import RAGAgent  # Import RAGAgent from agent.py
from .librarian import DataAgent

__all__ = ['RAGAgent', 'DataAgent']  # Export RAGAgent and DataAgent