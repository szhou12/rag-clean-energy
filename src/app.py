import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage 

load_dotenv()

# initialize chat_history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [] # a list to store HumanMessage objects

st.set_page_config(page_title="Clean Energy AI Consultant", page_icon=":robot:")

st.title("Clean Energy AI Consultant")

user_query = st.chat_input("Enter Your Question Here")
if user_query is not None and user_query != "":
    st.session_state.chat_history.append(HumanMessage(user_query))

    with st.chat_message("Human"):
        st.markdown(user_query)

    with st.chat_message("AI"):
        ai_response = "PLACEHOLDER"
        st.markdown(ai_response)