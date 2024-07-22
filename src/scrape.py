from dotenv import load_dotenv
# from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import Chroma
import requests
from llama_index.core import Document
from llama_index.core.node_parser import HTMLNodeParser
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core.node_parser import LangchainNodeParser
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

load_dotenv()

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


def save_vectorstore(docs):
    # docs = get_html_text_langchain(url)
    # Embeddings + create a Chroma db and store vectors (currently in-memory, not persistent)
    vector_store = Chroma.from_documents(docs, OpenAIEmbeddings())
    return vector_store


def get_context_retriever_chain(vector_store):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    retriever = vector_store.as_retriever()

    prompt = ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("human", "Given the above conversation, generate a search query to retrieve relevant information."),
    ])

    retriever_chain = create_history_aware_retriever(llm, retriever, prompt)
    return retriever_chain


def get_conversational_rag_chain(retriever_chain):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    # context = retrieved documents
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer the user's question based on the context below.\n\n{context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])

    stuff_documents_chain = create_stuff_documents_chain(llm, prompt)

    return create_retrieval_chain(retriever_chain, stuff_documents_chain)



# st.header("Scrape URL")
# website_url = st.text_input("Website URL")
# button_pressed = st.button("Scrape")
# if website_url is not None and website_url != "" and button_pressed:
#     # doc_nodes = get_html_text_llamaindex(website_url)
#     doc_nodes = get_html_text_langchain(website_url)
#     if doc_nodes:
#         st.write(doc_nodes)