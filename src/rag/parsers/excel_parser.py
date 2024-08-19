# rag/parsers/excel_parser.py
from rag.parsers.base_parser import BaseParser
import os
import pandas as pd
from langchain.document_loaders import UnstructuredMarkdownLoader

class ExcelParser(BaseParser):
    def save_file(self):
        """
        Save the Excel file (per sheet) to the directory = self.dir
        :return: The file path where the file is saved.
        """


    def load_file(self):
        """
        Load and parse the Excel file of multiple sheets.
        :return: List of lists of Langchain document objects.
        """
        docs = []
        excel_data = pd.read_excel(self.file, sheet_name=None)  # Read all sheets
        
        # iterate over each sheet
        for sheet_name, df in excel_data.items():

            # TODO: clean df before converting to markdown
            markdown_text = df.to_markdown(index=False)
            if not markdown_text:  # Skip empty sheets
                continue
            
            md_file_path = os.path.join(self.dir, f"{self.file_basename}_{sheet_name}.md")
            if not os.path.exists(md_file_path):
                print(f'Saving {sheet_name} sheet as md file to temp directory')
                with open(md_file_path, 'w') as f:
                    f.write(markdown_text)

            loader = UnstructuredMarkdownLoader(md_file_path, mode="elements")
            docs.append(loader.load())
        
        return docs