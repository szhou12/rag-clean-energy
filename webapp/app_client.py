import sys
import os
import streamlit as st
from langchain.schema import HumanMessage, AIMessage
from dotenv import load_dotenv
from utils import setup_logging
from rag import RAGAgent

# Add the src/ directory to the Python path in runtime
# sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# load_dotenv()
setup_logging()


# Set page configuration
st.set_page_config(page_title="Clean Energy AI Consultant", page_icon="\N{robot face}")

with st.sidebar:
    st.title("Settings")
    debug_on = st.toggle("Debug Mode")

    # Drop-down menu for LLM selection
    llm_choice = st.selectbox(
        "Select a LLM:",  # Label for the drop-down
        ["anthropic.claude-3-5-haiku-20241022-v1:0", 
         "anthropic.claude-3-5-sonnet-20241022-v2:0",
         "gpt-4o-mini"],
        index=0
    )

rag_agent = RAGAgent(llm_name=llm_choice, vector_db_persist_dir="/data/chroma")

# Title and heading
st.title("Clean Energy AI Consultant \N{robot face}")

# Chat history stored in session_state to persist across reloads
if "chat_history" not in st.session_state:
    # Initialize with a welcome message
    st.session_state.chat_history = [
        AIMessage(content="Hello, I am your Clean Energy AI Consultant. How can I assist you today?")
    ]

# Display chat messages from history
for message in st.session_state.chat_history:
    if isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)
    else:
        with st.chat_message("AI"):
            st.markdown(message.content)

    
# Input box for the user to type their question
user_query = st.chat_input("Enter Your Question Here")
if user_query:
    # Append the user query to the chat history
    with st.chat_message("Human"):
        st.markdown(user_query)
    st.session_state.chat_history.append(HumanMessage(content=user_query))

    # Call RAGAgent or fall back to a simpler response
    with st.chat_message("AI"):
        with st.spinner("AI Agent is thinking..."):

            if debug_on:
                retrieved_docs_runnable = rag_agent._retrieve_bilingual_contextual_docs()
                retrieved_docs = retrieved_docs_runnable.invoke({
                    "chat_history": st.session_state.chat_history[-1:],
                    "input": user_query
                })
                st.expander("Retrieved Documents").write(retrieved_docs)
            
            ai_response = st.write_stream(rag_agent.handle_query(user_query, st.session_state.chat_history[-1:]))

    # Append the AI response to the chat history
    st.session_state.chat_history.append(AIMessage(content=ai_response))
