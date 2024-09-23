import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyMuPDFLoader, UnstructuredExcelLoader
import os
from rag.parsers import ExcelParser

import scrape
import upload

load_dotenv() # Load environment variables from .env file



# show in the tab
st.set_page_config(page_title="Clean Energy AI Consultant", page_icon="\N{robot face}")


st.title("Clean Energy AI Consultant \N{robot face}")


def get_rag_response(user_query, chat_history):
    retriever_chain = scrape.get_context_retriever_chain(st.session_state.vector_store)

    # conversational_rag_chain = LCEL Runnable
    conversational_rag_chain = scrape.get_conversational_rag_chain(retriever_chain)
    chain = conversational_rag_chain.pick("answer")

    response = chain.stream({
        "chat_history": chat_history,
        "input": user_query
    })

    # return response["answer"] # use this if use conversational_rag_chain.invoke()
    return response


def get_rag_response_pdf(user_query, chat_history):
    retriever_chain = upload.get_context_retriever_chain(st.session_state.vector_store)

    # conversational_rag_chain = LCEL Runnable
    conversational_rag_chain = upload.get_conversational_rag_chain(retriever_chain)
    chain = conversational_rag_chain.pick("answer")

    response = chain.stream({
        "chat_history": chat_history,
        "input": user_query
    })

    # return response["answer"] # use this if use conversational_rag_chain.invoke()
    return response

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


for message in st.session_state.chat_history:
    if isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)
    else:
        with st.chat_message("AI"):
            st.markdown(message.content)



# if website_url is not None and website_url != "":
#     if "vector_store" not in st.session_state:
#         doc_nodes = scrape.get_html_text_langchain(website_url)
#         vector_store = scrape.save_vectorstore(doc_nodes)
#         st.session_state.vector_store = vector_store
    

#     user_query = st.chat_input("Enter Your Question Here")
#     if user_query is not None and user_query != "":
#         # ai_response = st.write_stream(get_ai_response(user_query, st.session_state.chat_history))
#         ai_response = get_rag_response(user_query)


#         st.session_state.chat_history.append(HumanMessage(content=user_query))
#         st.session_state.chat_history.append(AIMessage(content=ai_response))



user_query = st.chat_input("Enter Your Question Here")
if user_query is not None and user_query != "":

    
    with st.chat_message("Human"):
        st.markdown(user_query)
    st.session_state.chat_history.append(HumanMessage(content=user_query))

    with st.chat_message("AI"):
        if "vector_store" not in st.session_state:
            ai_response = st.write_stream(get_ai_response(user_query, st.session_state.chat_history))
        else:
            # ai_response = st.write_stream(get_rag_response(user_query, st.session_state.chat_history))
            ai_response = st.write_stream(get_rag_response_pdf(user_query, st.session_state.chat_history))
            # st.write(ai_response) 
    
    st.session_state.chat_history.append(AIMessage(content=ai_response))




with st.sidebar:
    st.header("Scrape URL")
    website_url = st.text_input("Website URL")
    button_pressed = st.button("Scrape")

    if website_url is not None and website_url != "" and button_pressed:
        st.write("Scraping...")
        doc_nodes = scrape.get_html_text_langchain(website_url)
        vector_store = scrape.save_vectorstore(doc_nodes)
        st.session_state.vector_store = vector_store
        st.write("Scraping Completed!")
    #     # doc = get_doc_from_url(website_url)
    #     doc_nodes = scrape.get_html_text_langchain(website_url)
    #     if doc_nodes:
    #         st.write(doc_nodes)


    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "xlsx", "docx", "txt"])
    if uploaded_file is not None:
        # # doc_nodes = upload.get_pdf_text_langchain(uploaded_file)
        # doc_nodes_list = upload.split_text_langchain(uploaded_file)
        # # vector_store = upload.save_vectorstore(doc_nodes)
        # vector_store = upload.create_vectorstore()
        # for doc_nodes in doc_nodes_list:
        #     # doc_nodes = list of Document objects
        #     upload.add_to_vectorstore(vector_store, doc_nodes)
        # st.session_state.vector_store = vector_store
        # st.write("File Uploaded and Parsed Successfully!")

        #### Step 1 - Save to /temp ####
        temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')
        file_path = os.path.join(temp_dir, uploaded_file.name)
        if not os.path.exists(file_path):
            print('Saving file to temp directory')
            with open(os.path.join(temp_dir, uploaded_file.name), mode='wb') as w:
                w.write(uploaded_file.getvalue())
        

        #### Step 2 - Load PDF by PyMuPDF using file_path <str> ####
        ## 1 document = 1 page. e.g. if 36 pages, then list of 36 documents
        # loader = PyMuPDFLoader(file_path)
        # doc = loader.load()
        # st.write(f"Total loaded documents: {len(doc)}")
        # st.write(f"One loaded document Metadata: \n{doc[0].metadata}")
        # st.write(f"One loaded document page_content: \n{doc[0].page_content}")

        #### Step 2 - Load EXCEL by UnstructuredExcelLoader using file_path <str> ####
        parser = ExcelParser(uploaded_file)
        docs = parser.load_and_parse()
        st.write(f"Total loaded documents: {len(docs)}")
        st.write(f"One loaded document Metadata: \n{docs[0].metadata}")
        st.write(f"One loaded document page_content: \n{docs[0].page_content}")
        


        

        