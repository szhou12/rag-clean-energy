# rag/parsers/pdf_parser.py
import os
from rag.parsers.base_parser import BaseParser
from langchain_community.document_loaders import PyMuPDFLoader

class PDFParser(BaseParser):
    def save_file(self):
        """
        Save the PDF file to the directory = self.dir
        :return: The file path where the file is saved.
        """
        # Create the directory if it does not exist yet
        if not os.path.exists(self.dir):
            os.makedirs(self.dir, exist_ok=True)

        file_path = os.path.join(self.dir, self.file.name)
        
        if not os.path.exists(file_path):
            print(f'Saving {self.file_ext} file to directory: {self.dir}')
            with open(file_path, mode='wb') as w:
                w.write(self.file.getvalue())
        
        return file_path


    def load_and_parse(self):
        """
        Load and parse the PDF file.
        :return: List of Langchain Document objects.
        """
        file_path = self.save_file()
        loader = PyMuPDFLoader(file_path)
        docs = loader.load()
        # docs = List[Document]
        return docs