import streamlit as st
# from dotenv import load_dotenv
# from langchain_core.messages import HumanMessage, AIMessage
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import WebBaseLoader
import requests
from llama_index.core import Document
from llama_index.core.node_parser import HTMLNodeParser
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core.node_parser import LangchainNodeParser


# Use llama_index HTMLNodeParser to extract HTML content
def get_html_text_llamaindex(url):
    response = requests.get(url) # get HTML content from the URL
    # print(response)
    # print(response.text)
    if response.status_code == 200:
        # Extract the HTML content from the response. i.e. with tags and all that. same to inspect
        html_doc = response.text
        # Create a Document object with the HTML content
        document = Document(id_=url, text=html_doc)
        # Initialize the HTMLNodeParser with optional list of tags
        parser = HTMLNodeParser()
        # Parse nodes from the HTML document
        nodes = parser.get_nodes_from_documents([document])
        return nodes
    else:
        return None
    

# Use LangChain to extract HTML content
def get_html_text_langchain(url):
    loader = WebBaseLoader(url)
    doc = loader.load()
    text_splitter = RecursiveCharacterTextSplitter()
    doc_chunks = text_splitter.split_documents(doc)
    return doc_chunks



st.header("Scrape URL")
website_url = st.text_input("Website URL")
button_pressed = st.button("Scrape")
if website_url is not None and website_url != "" and button_pressed:
    # doc_nodes = get_html_text_llamaindex(website_url)
    doc_nodes = get_html_text_langchain(website_url)
    if doc_nodes:
        st.write(doc_nodes)