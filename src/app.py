import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage 

load_dotenv()

# initialize chat_history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [] # a list to store HumanMessage objects

st.set_page_config(page_title="Clean Energy AI Consultant", page_icon=":robot:")

st.title("Clean Energy AI Consultant")


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
    st.session_state.chat_history.append(HumanMessage(user_query))

    # init a streamlit prompt context annotated with "Human"
    with st.chat_message("Human"):
        st.markdown(user_query)

    with st.chat_message("AI"):
        ai_response = "PLACEHOLDER"
        st.markdown(ai_response)
    
    st.session_state.chat_history.append(AIMessage(ai_response))