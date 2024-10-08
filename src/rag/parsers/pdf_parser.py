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
        
        if not os.path.exists(self.filepath):
            print(f'Saving {self.file.name} to directory: {self.dir}')
            with open(self.filepath, mode='wb') as w:
                w.write(self.file.getvalue())
        
        return self.filepath


    def load_and_parse(self):
        """
        Load and parse the PDF file from a file path.
        Note: 1 document = 1 page. e.g. if a file has 36 pages, then return a list of 36 documents

        :return: Tuple[List[Document], List[Dict]] - A list of Langchain Document objects and their corresponding metadata.
        """
        loader = PyMuPDFLoader(self.filepath)
        docs = loader.load()

        metadata = [{"source": self.filename, "page": doc.metadata.get('page', None)} for doc in docs]

        return docs, metadata