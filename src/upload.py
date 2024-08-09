import os
import pandas as pd
from langchain_community.document_loaders import PyMuPDFLoader, UnstructuredExcelLoader, UnstructuredMarkdownLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
# from langchain.vectorstores import utils as chromautils
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def save_and_load_file(file):
    temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')

    
    file_basename, file_ext = os.path.splitext(file.name)  # Get the file extension

    

    # Function to check the file type
    def load_file_type(file_ext):
        if file_ext.lower() == '.pdf':

            file_path = os.path.join(temp_dir, file.name)
            if not os.path.exists(file_path):
                print('Saving pdf file to temp directory')
                with open(file_path, mode='wb') as w:
                    w.write(file.getvalue())

            # NOTE: PyMuPDFLoader takes ONLY the file path (str) as an argument. So need to save the file to local before loading
            loader = PyMuPDFLoader(file_path)
        elif file_ext.lower() in ['.xls', '.xlsx']:
            df = pd.read_excel(file)
            markdown_text = df.to_markdown(index=False)

            md_file_path = os.path.join(temp_dir, file_basename+".md")
            if not os.path.exists(md_file_path):
                print('Saving md file to temp directory')
                with open(md_file_path, 'w') as f:
                    f.write(markdown_text)

            loader = UnstructuredMarkdownLoader(md_file_path, mode="elements") # mode="elements" creates html-like table to present the data
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        return loader.load()
    
    try:
        doc = load_file_type(file_ext)
    except ValueError as e: # re-raise it to let it propagate to whoever calls save_and_parse_file()
        raise e
    
    return doc

def split_text_langchain(file):
    

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
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len
    )

    try:
        doc = save_and_load_file(file)
        doc_chunks = text_splitter.split_documents(doc)
    except ValueError as e: 
        print(e)
        raise

    return doc_chunks


# def get_excel_text_langchain(file):
#     # Define the path to the temp directory
#     temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')

#     file_path = os.path.join(temp_dir, file.name)

#     df = pd.read_excel(file_path)


#     if not os.path.exists(file_path):
#         print('Saving file to temp directory')
#         with open(os.path.join(temp_dir, file.name), mode='wb') as w:
#             w.write(file.getvalue())

#     df = pd.read_excel(file_path)


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
    doc = loader.load()

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
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len
    )

    doc_chunks = text_splitter.split_documents(doc)

    return doc_chunks

def save_vectorstore(chunks):
    # chunks = get_html_text_langchain(url)
    # Embedding model to transcribe test to vectors
    embedding_model = OpenAIEmbeddings()


    #  Create a Chroma db and store vectors (currently in-memory, not persistent)
    #  Need filter_complex_metadata(chunks) to filter out non-textual data
    # TODO: persist to disk
    vector_store = Chroma.from_documents(filter_complex_metadata(chunks), embedding_model)
    return vector_store

def get_context_retriever_chain(vector_store):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    retriever = vector_store.as_retriever()

    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, "
        "just reformulate it if needed and otherwise return it as is."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])

    retriever_chain = create_history_aware_retriever(llm, retriever, prompt)
    return retriever_chain


def get_conversational_rag_chain(retriever_chain):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    template = """
        Your answer should be in the format of a report that follows the structure: 
        <Title>: give a proper title
        <Summary>: key points that should be highlighted
        <Details>: provide details to each key point and enrich the details with numbers and statistics
        <Conclusion>: give a proper conclusion
        """
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Combine the given chat history and the following pieces of retrieved context to answer the user's question.\n\n{context}"), # context = retriever_chain
        ("system", template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"), # input = user query
    ])

    stuff_documents_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever_chain, stuff_documents_chain)

    return rag_chain