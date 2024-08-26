# rag/parsers/base_parser.py
import os
from abc import ABC, abstractmethod

# ABC in BaseParser(ABC) defines the BaseParser class as an abstract class
class BaseParser(ABC):
    def __init__(self, file, dir=None):
        self.file = file
        self.file_basename, self.file_ext = os.path.splitext(self.file.name)
        # TODO: AFTER setup databse, use env variable to store the directory path
        self.dir = dir or os.path.join(os.getcwd(), 'temp')
    
    @abstractmethod
    def save_file(self):
        """
        Save the uploaded file to the directory = self.dir.
        Must be implemented by subclasses.
        
        :return: The file path where the file is saved.
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    
    @abstractmethod
    def load_and_parse(self):
        """
        Load the file. MUST be implemented by subclasses.
        :return: List of lists of Langchain document objects. [List[Document], List[Document], ...]
        """
        raise NotImplementedError("Subclasses must implement this method")