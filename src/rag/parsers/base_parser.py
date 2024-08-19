# rag/parsers/base_parser.py
import os
from abc import ABC, abstractmethod

class BaseParser:
    def __init__(self, file, dir=None):
        self.file = file
        self.file_basename, self.file_ext = os.path.splitext(self.file.name)
        self.dir = dir or os.path.join(os.path.dirname(__file__), '..', 'temp')

        # Create the directory if it does not exist yet
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)
    
    @abstractmethod
    def save_file(self):
        """
        Save the uploaded file to the directory = self.dir.
        Must be implemented by subclasses.
        
        :return: The file path where the file is saved.
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    
    @abstractmethod
    def load_file(self):
        """
        Load the file. MUST be implemented by subclasses.
        :return: List of lists of Langchain document objects. [List[Document], List[Document], ...]
        """
        raise NotImplementedError("Subclasses must implement this method")