import streamlit as st
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from rag import RAGAgent
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI

load_dotenv()

# mysql_config = {
#         'user': 'root',
#         'host': 'localhost',
#         'port': 3306,
#         'password': os.getenv('MYSQL_PASSWORD'),
#         'db_name': 'rmi_test'
#     }
    
# Initialize RAGAgent (ensure to pass necessary MySQL config)
# rag_agent = RAGAgent(mysql_config=mysql_config, vector_db="db_chroma")
rag_agent = RAGAgent(vector_db="db_chroma")



# Set page configuration
st.set_page_config(page_title="Clean Energy AI Consultant", page_icon="\N{robot face}")

# Title and heading
st.title("Clean Energy AI Consultant \N{robot face}")



# Initialize vector_store in session_state if not already set
# if "vector_store" not in st.session_state:
#     st.session_state.vector_store = rag_agent.vector_store

# Chat history stored in session_state to persist across reloads
if "chat_history" not in st.session_state:
    # Initialize with a welcome message
    st.session_state.chat_history = [
        AIMessage(content="Hello, I am your Clean Energy AI Consultant. How can I assist you today?")
    ]

# Function to handle AI response from chat input
def get_ai_response(user_query, chat_history):
    template = """
    You are a professional consultant in the domain of clean energies. 
    Please answer the following question by considering the history of the conversation:

    Chat history: {chat_history}

    User question: {user_question}
    """
    prompt = ChatPromptTemplate.from_template(template)

    # Initialize the LLM (Language Model)
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    # Build the workflow using LangChain's LCEL
    workflow_chain = prompt | llm | StrOutputParser()

    # Stream the response from the LLM
    response = workflow_chain.stream({
        "user_question": user_query,
        "chat_history": chat_history
    })

    return response


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
        # if "vector_store" not in st.session_state:  # Fallback to simple AI response
        #     st.write("NOT triggering RAG Agent!!!")
        #     ai_response = st.write_stream(get_ai_response(user_query, st.session_state.chat_history))
        # else:  # Use the RAGAgent's handle_query method to get response
        #     st.write("triggering RAG Agent...")

        #     #### Debug by inspecting ####
        #     # TODO: retrieved_docs_runnable = rag_agent._retrieve_contextual_docs()
        #     retrieved_docs_runnable = rag_agent._retrieve_bilingual_contextual_docs()
        #     # Execute the Runnable to get the list of Documents
        #     retrieved_docs = retrieved_docs_runnable.invoke({
        #         "chat_history": st.session_state.chat_history,
        #         "input": user_query
        #     })
        #     st.write(retrieved_docs)
            
        #     ai_response = st.write_stream(rag_agent.handle_query(user_query, st.session_state.chat_history))
        st.write("triggering RAG Agent...")
        #### Debug by inspecting ####
        # TODO: retrieved_docs_runnable = rag_agent._retrieve_contextual_docs()
        retrieved_docs_runnable = rag_agent._retrieve_bilingual_contextual_docs()
        # Execute the Runnable to get the list of Documents
        retrieved_docs = retrieved_docs_runnable.invoke({
            "chat_history": st.session_state.chat_history,
            "input": user_query
        })
        st.write(retrieved_docs)
        
        ai_response = st.write_stream(rag_agent.handle_query(user_query, st.session_state.chat_history))

    # Append the AI response to the chat history
    st.session_state.chat_history.append(AIMessage(content=ai_response))

# Sidebar for scraping URL functionality
# with st.sidebar:

#     ## File Upload
#     uploaded_file = st.file_uploader("Choose a file", type=["pdf", "xlsx", "xls"])
#     if uploaded_file is not None:
#         temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')
#         file_path = os.path.join(temp_dir, uploaded_file.name)
#         if not os.path.exists(file_path):
#             print('Saving file to temp directory')
#             with open(os.path.join(temp_dir, uploaded_file.name), mode='wb') as w:
#                 w.write(uploaded_file.getvalue())
#             st.write(f"Saved to filepath: {file_path}")
#         rag_agent.process_file(file_path)

#     ## URL Scraping
#     url = st.text_input("Website URL")
#     max_pages = st.number_input("Maximum number of pages to scrape:", min_value=1, value=1)
#     autodownload = st.checkbox("Enable autodownload of attached files", value=False)
#     language = st.selectbox("Select Language", options=["en", "zh"], index=0)

#     # Button to start scraping
#     if st.button("Start Scraping"):
#         if url:
#             with st.spinner("Scraping..."):
#                 try:
#                     # Call the RAGAgent's process_url method to scrape content
#                     num_docs, num_downloaded_files = rag_agent.process_url(url, max_pages=max_pages, autodownload=autodownload, language=language)

#                     # Display the scraping results
#                     st.success(f"Scraping completed! {num_docs} pages scraped.")
#                     if autodownload:
#                         st.write(f"Files downloaded: {num_downloaded_files}")

#                     # Display scraped URLs from the scraper
#                     st.write("Scraped URLs:")
#                     for url in rag_agent.scraper.scraped_urls:
#                         st.write(url)

#                 except Exception as e:
#                     st.error(f"An error occurred: {e}")
#         else:
#             st.warning("Please enter a valid URL.")