import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import WebBaseLoader


load_dotenv() # Load environment variables from .env file

# initialize chat_history stored in session_state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [] # a list to store HumanMessage & AIMessage objects

st.set_page_config(page_title="Clean Energy AI Consultant", page_icon="\N{robot face}")

st.title("Clean Energy AI Consultant \N{robot face}")


def get_doc_from_url(url):
    '''
    Scrape the website's content from the given URL
    '''
    loader = WebBaseLoader(url)
    doc = loader.load()
    return doc

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
        model="gpt-3.5-turbo",
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
        doc = get_doc_from_url(website_url)
        st.write(doc)
            