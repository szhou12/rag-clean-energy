import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

import scrape

load_dotenv() # Load environment variables from .env file



# show in the tab
st.set_page_config(page_title="Clean Energy AI Consultant", page_icon="\N{robot face}")



st.title("Clean Energy AI Consultant \N{robot face}")



def get_rag_response(user_query):
    retriever_chain = scrape.get_context_retriever_chain(st.session_state.vector_store)

    conversational_rag_chain = scrape.get_conversational_rag_chain(retriever_chain)

    ai_response = conversational_rag_chain.invoke({
        "chat_history": st.session_state.chat_history,
        "input": user_query
    })

    return ai_response['answer']

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
    # a list to store HumanMessage & AIMessage objects
    st.session_state.chat_history = [
        AIMessage(content="Hello, I am your Clean Energy AI Consultant. How can I help you?")
    ]



with st.sidebar:
    st.header("Scrape URL")
    website_url = st.text_input("Website URL")
    # button_pressed = st.button("Scrape")

    # if website_url is not None and website_url != "" and button_pressed:
    #     # doc = get_doc_from_url(website_url)
    #     doc_nodes = scrape.get_html_text_langchain(website_url)
    #     if doc_nodes:
    #         st.write(doc_nodes)

if website_url is not None and website_url != "":
    if "vector_store" not in st.session_state:
        doc_nodes = scrape.get_html_text_langchain(website_url)
        vector_store = scrape.save_vectorstore(doc_nodes)
        st.session_state.vector_store = vector_store
    

    

    user_query = st.chat_input("Enter Your Question Here")
    if user_query is not None and user_query != "":
        # ai_response = st.write_stream(get_ai_response(user_query, st.session_state.chat_history))
        ai_response = get_rag_response(user_query)


        st.session_state.chat_history.append(HumanMessage(content=user_query))
        st.session_state.chat_history.append(AIMessage(content=ai_response))

    


for message in st.session_state.chat_history:
    if isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)
    else:
        with st.chat_message("AI"):
            st.markdown(message.content)
