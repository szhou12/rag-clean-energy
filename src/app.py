import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import WebBaseLoader
import requests
from llama_index.core import Document
from llama_index.core.node_parser import HTMLNodeParser

load_dotenv() # Load environment variables from .env file



# show in the tab
st.set_page_config(page_title="Clean Energy AI Consultant", page_icon="\N{robot face}")



st.title("Clean Energy AI Consultant \N{robot face}")


def get_doc_from_url(url):
    '''
    Scrape the website's content from the given URL
    '''
    loader = WebBaseLoader(url)
    doc = loader.load()
    return doc

def get_html_text(url):
    response = requests.get(url) # get HTML content from the URL
    # print(response)
    # print(response.text)
    if response.status_code == 200:
        # Extract the HTML content from the response. i.e. with tags and all that. same to inspect
        html_doc = response.text
        # Create a Document object with the HTML content
        document = Document(id_=url, text=html_doc)
        # Initialize the HTMLNodeParser with optional list of tags
        parser = HTMLNodeParser(tags=["p", "h1"])
        # Parse nodes from the HTML document
        nodes = parser.get_nodes_from_documents([document])
        return nodes
    else:
        return None




# Get AI Response
def get_ai_response(user_query, chat_history):
    template = """
    You are a professional consultant in the domain of clean energies. 
    Please answer the following question by considering the history of the conversation:

    Chat history: {chat_history}

    User question: {user_question}
    """

    prompt = ChatPromptTemplate.from_template(template)

    # If not explicitly specified, it will by default load the env var by the key "OPENAI_API_KEY" 
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    # LangChain Expression Language (LCEL)
    workflow_chain = prompt | llm | StrOutputParser()


    # Add streaming feature: returns a Generator object
    response = workflow_chain.stream({
        "user_question": user_query,
        "chat_history": chat_history
    })

    return response


# initialize chat_history stored in session_state to persist for each reload
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [] # a list to store HumanMessage & AIMessage objects


# Conversation Display between User and AI
# NOTE: This block has to be placed before "User Input" block. Think of this block as displaying all previously stored messages.
for message in st.session_state.chat_history:
    if isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)
    else:
        with st.chat_message("AI"):
            st.markdown(message.content)


# User Input
# NOTE: Display and Store current round of user input and AI response
user_query = st.chat_input("Enter Your Question Here")
if user_query is not None and user_query != "":
    st.session_state.chat_history.append(HumanMessage(content=user_query))

    # init a streamlit prompt context annotated with "Human"
    with st.chat_message("Human"):
        st.markdown(user_query)

    with st.chat_message("AI"):
       # streamlit output AI response in real-time (streaming manner).
       # st.write_stream() supports only sync streaming
       # full response text is stored in ai_response
       ai_response = st.write_stream(get_ai_response(user_query, st.session_state.chat_history))
    
    st.session_state.chat_history.append(AIMessage(content=ai_response))



with st.sidebar:
    st.header("Scrape URL")
    website_url = st.text_input("Website URL")
    button_pressed = st.button("Scrape")
    if website_url is not None and website_url != "" and button_pressed:
        # doc = get_doc_from_url(website_url)
        doc_nodes = get_html_text(website_url)
        if doc_nodes:
            st.write(doc_nodes)
                