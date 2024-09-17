# rag/parsers/excel_parser.py
from rag.parsers.base_parser import BaseParser
import os
import pandas as pd
from langchain_community.document_loaders import UnstructuredMarkdownLoader

class ExcelParser(BaseParser):
    def save_file(self, sheet_name, markdown_text):
        """
        Save the Excel file (per sheet) in Markdown format to the directory = self.dir
        :return: The file path where the file is saved.
        """
        # Create the directory if it does not exist yet
        if not os.path.exists(self.dir):
            os.makedirs(self.dir, exist_ok=True)
            
        md_file_path = os.path.join(self.dir, f"{self.file_basename}_{sheet_name}.md")
        if not os.path.exists(md_file_path):
            print(f'Saving {sheet_name} sheet as md file to temp directory')
            with open(md_file_path, 'w') as f:
                f.write(markdown_text)
        
        return md_file_path


    def load_and_parse(self):
        """
        Load and parse the Excel file of multiple sheets.
        :return: List of Langchain Document objects.
        """
        docs = []
        excel_data = pd.read_excel(self.file, sheet_name=None)  # Read all sheets
        
        # iterate over each sheet
        for sheet_name, df in excel_data.items():
            if df.empty: # Skip empty sheets
                continue

            df = self.clean_df(df)
            markdown_text = df.to_markdown(index=False)
            
            file_path = self.save_file(sheet_name, markdown_text)

            loader = UnstructuredMarkdownLoader(file_path, mode="elements")
            docs.extend(loader.load())
        
        # docs = List[Document]
        return docs
    
    def clean_df(self, df):
        """
        Clean the DataFrame before converting to markdown.
        """
        df.dropna(how='all', inplace=True)  # Drop rows where all cells are empty
        df.dropna(axis=1, how='all', inplace=True)  # Drop columns where all cells are empty
        df.fillna('', inplace=True)  # Replace NaN cells with empty strings
        return df