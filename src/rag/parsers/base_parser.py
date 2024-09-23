# rag/parsers/base_parser.py
import os
from abc import ABC, abstractmethod

# ABC in BaseParser(ABC) defines the BaseParser class as an abstract class
class BaseParser(ABC):
    def __init__(self, file, dir=None):
        """
        Initialize the BaseParser object.

        :param file: The uploaded / auto-downloaded file object.
        :param dir: The directory to save the file. Default is 'temp'.
        """
        self.file = file
        self.file_basename, self.file_ext = os.path.splitext(self.file.name)
        # TODO: AFTER setup databse, use env variable to store the directory path. necessary or not???
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

        :return: List[Document] - List of Langchain Document objects.
        """
        raise NotImplementedError("Subclasses must implement this method")