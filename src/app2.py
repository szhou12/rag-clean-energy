import streamlit as st
from dotenv import load_dotenv
from rag import RAGAgent

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI



# show in the tab
st.set_page_config(page_title="Clean Energy AI Consultant", page_icon="\N{robot face}")


st.title("Clean Energy AI Consultant \N{robot face}")

rag_agent = RAGAgent()

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


for message in st.session_state.chat_history:
    if isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)
    else:
        with st.chat_message("AI"):
            st.markdown(message.content)


user_query = st.chat_input("Enter Your Question Here")
if user_query is not None and user_query != "":

    
    with st.chat_message("Human"):
        st.markdown(user_query)
    st.session_state.chat_history.append(HumanMessage(content=user_query))

    with st.chat_message("AI"):
        if "vector_store" not in st.session_state: # blank AI response without RAG
            ai_response = st.write_stream(get_ai_response(user_query, st.session_state.chat_history))
        else:
            ai_response = st.write_stream(rag_agent.handle_query(user_query, st.session_state.chat_history)) 
    
    st.session_state.chat_history.append(AIMessage(content=ai_response))


with st.sidebar:
    st.header("Scrape URL")
    url = st.text_input("Website URL")
    max_pages = st.number_input("Maximum number of pages to scrape:", min_value=1, value=1)
    autodownload = st.checkbox("Enable autodownload of attached files", value=False)
    

    # Button to start scraping
    if st.button("Start Scraping"):
        if url:
            with st.spinner("Scraping..."):
                try:
                    # Call the scrape method
                    num_docs, num_downloaded_files = rag_agent.process_url(url, max_pages=max_pages, autodownload=autodownload)
                    
                    # Display results
                    st.success(f"Scraping completed! {num_docs} pages scraped.")
                    
                    if autodownload:
                        st.write(f"Files downloaded: {num_downloaded_files}")
                        # for file in downloaded_files:
                        #     st.write(file)
                            
                    st.write("scraped URL:")
                    for url in rag_agent.scraper.scraped_urls:
                        st.write(url)
                    # Optionally, display document contents (this could be a lot of text!)
                    # st.write("Sample of scraped content:")
                    # for i, doc in enumerate(documents[:3]):  # Displaying the first 3 documents
                    #     st.write(f"Document {i+1}:")
                    #     st.write(doc)
                 
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.warning("Please enter a valid URL.")

