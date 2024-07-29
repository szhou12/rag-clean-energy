from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os


def get_pdf_text_langchain(file):
    # Define the path to the temp directory
    temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')

    file_path = os.path.join(temp_dir, file.name)
    if not os.path.exists(file_path):
        print('Saving file to temp directory')
        with open(os.path.join(temp_dir, file.name), mode='wb') as w:
            w.write(file.getvalue())

    # NOTE: PyMuPDFLoader takes ONLY the file path (str) as an argument. So need to save the file to local before loading
    loader = PyMuPDFLoader(file_path)
    data = loader.load()

    # Add additional separators customizing for Chinese texts
    # Ref: https://python.langchain.com/v0.1/docs/modules/data_connection/document_transformers/recursive_text_splitter/
    text_splitter = RecursiveCharacterTextSplitter(
        separators=[
            "\n\n",
            "\n",
            " ",
            ".",
            ",",
            "\u200b",  # Zero-width space
            "\uff0c",  # Fullwidth comma
            "\u3001",  # Ideographic comma
            "\uff0e",  # Fullwidth full stop
            "\u3002",  # Ideographic full stop
            "",
        ],
        # Existing args
    )
    

    return data[0]