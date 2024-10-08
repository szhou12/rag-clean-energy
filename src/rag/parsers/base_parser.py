# rag/parsers/base_parser.py
import os
from abc import ABC, abstractmethod
from typing import List, Literal
from langchain.schema import Document

# ABC in BaseParser(ABC) defines the BaseParser class as an abstract class

class BaseParser(ABC):
    BINARY_EXTENSIONS = {'.pdf', '.xls', '.xlsx'}
    TEXT_EXTENSIONS = {'.txt', '.md', '.csv'}
    def __init__(self, filepath: str, dir: str = None):
        """
        Initialize the BaseParser object with a file path.

        :param filepath: String path to the file.
        :param dir: The directory to save the file. Default is 'temp' in the current working directory.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"The file {filepath} does not exist.")
        
        self.filepath = filepath
        self.filename = os.path.basename(self.filepath) # filename with extension
        self.file_basename, self.file_ext = os.path.splitext(self.filename)

        self.mode: Literal['r', 'rb'] = self._determine_file_mode()
        self.file = open(self.filepath, self.mode)

        # TODO: AFTER cloud deploy, save to Object Storage
        self.dir = dir or os.path.join(os.getcwd(), 'temp')
        os.makedirs(self.dir, exist_ok=True)
    
    def _determine_file_mode(self) -> Literal['r', 'rb']:
        """
        Determine the file mode based on the file extension.
        """
        if self.file_ext.lower() in self.BINARY_EXTENSIONS:
            return 'rb'
        elif self.file_ext.lower() in self.TEXT_EXTENSIONS:
            return 'r'
        else:
            raise ValueError(f"Unsupported file type: {self.filepath}")

    def __enter__(self):
        """Enable use of 'with' statement for resource management."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure the file is closed when exiting a 'with' block."""
        self.close()

    def close(self):
        """Close the file if it's open."""
        if hasattr(self, 'file') and not self.file.closed:
            self.file.close()

    def __del__(self):
        """Ensure the file is closed when the parser object is destroyed."""
        self.close()
    
    @abstractmethod
    def save_file(self) -> str:
        """
        Save the uploaded file to the directory specified by self.dir.
        Must be implemented by subclasses.
        
        :return: The file path where the file is saved.
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    @abstractmethod
    def load_and_parse(self) -> List[Document]:
        """
        Load and parse the file. Must be implemented by subclasses.

        :return: List of Langchain Document objects.
        """
        raise NotImplementedError("Subclasses must implement this method")