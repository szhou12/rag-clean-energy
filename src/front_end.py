import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from db_mysql import MySQLManager
from rag import RAGAgent
from rag import DataAgent

# data = [
#     {
#         'id': 1,
#         'source': '/Users/shuyuzhou/Documents/github/rag-clean-energy/src/../temp/TheStateofCleanTechnologyManufacturing.pdf',
#         'page': '0',
#         'date': '2024-10-08 16:01:11',
#         'language': 'en',
#     },
#     {
#         'id': 2,
#         'source': '/Users/shuyuzhou/Documents/github/rag-clean-energy/src/../temp/TheStateofCleanTechnologyManufacturing.pdf',
#         'page': '1',
#         'date': '2024-10-08 16:01:11',
#         'language': 'en',
#     },
#     {
#         'id': 3,
#         'source': '/Users/shuyuzhou/Documents/github/rag-clean-energy/src/../temp/TheStateofCleanTechnologyManufacturing.pdf',
#         'page': '2',
#         'date': '2024-10-08 16:01:11',
#         'language': 'en',
#     },
#     {
#         'id': 4,
#         'source': '/Users/shuyuzhou/Documents/github/rag-clean-energy/src/../temp/TheStateofCleanTechnologyManufacturing.pdf',
#         'page': '3',
#         'date': '2024-10-08 16:01:11',
#         'language': 'en',
#     }
# ]

load_dotenv()

mysql_config = {
        'user': 'root',
        'host': 'localhost',
        'port': 3306,
        'password': os.getenv('MYSQL_PASSWORD'),
        'db_name': 'rmi_test'
    }


# rag_agent = RAGAgent(mysql_config=mysql_config, vector_db="db_chroma")
# data = rag_agent.get_file_metadata()

data_agent = DataAgent(mysql_config=mysql_config, vector_db="db_chroma")
data = data_agent.get_file_metadata()


# Function to extract file name from the full path
def get_filename_from_path(filepath):
    return os.path.basename(filepath)

# Set up the Streamlit page
st.set_page_config(page_title="Data Table", layout="wide")


tab1, tab2 = st.tabs(["Web", "File"])

with tab1:
    st.title("Web Page")
    st.write("In Development...")


with tab2:
    # Add a title
    st.title("Data Table For Uploaded Files")

    # Initialize session state for the DataFrame if it doesn't exist
    if 'df' not in st.session_state:
        # Modify the data to include only the filename instead of the full path
        for row in data:
            row['source'] = get_filename_from_path(row['source'])  # Replace source with the filename
        
        st.session_state.df = pd.DataFrame(data)

    # Create a copy of the DataFrame for display
    display_df = st.session_state.df.copy()


    # Display the data as an editable table
    display_df['Delete'] = False  # Add a default "Delete" column with checkboxes (False by default)

    # Display the data as an editable table and capture the edited dataframe
    edited_df = st.data_editor(
        display_df,
        hide_index=True,
        column_config={
            "Delete": st.column_config.CheckboxColumn(
                "Delete",
                help="Select to delete",
                default=False,
            ),
            "source": "File Name",  # Rename 'source' column to 'File Name'
            "total_records": "Total Pages/Sheets"
        },
        disabled=["source", "date", "language", "total_records"],  # Disable editing on these columns
        key="data_editor",
    )

    # Add a button to apply deletions
    if st.button("Delete Selected Rows"):
        # Use the edited dataframe to determine which rows to delete
        rows_to_keep = edited_df[~edited_df['Delete']]
        
        # Update the session state DataFrame
        st.session_state.df = rows_to_keep.drop(columns=['Delete']).reset_index(drop=True)
        
        st.success("Selected rows have been deleted.")
        st.rerun()  # Rerun the script to reflect changes immediately


with st.sidebar:

    ## File Upload
    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "xlsx", "xls"])
    if uploaded_file is not None:
        temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')
        file_path = os.path.join(temp_dir, uploaded_file.name)
        if not os.path.exists(file_path):
            print('Saving file to temp directory')
            with open(os.path.join(temp_dir, uploaded_file.name), mode='wb') as w:
                w.write(uploaded_file.getvalue())
            st.write(f"Saved to filepath: {file_path}")
        # rag_agent.process_file(file_path)
        data_agent.process_file(file_path)

        st.success(f"File uploaded and parsed!")

    ## URL Scraping
    url = st.text_input("Website URL")
    max_pages = st.number_input("Maximum number of pages to scrape:", min_value=1, value=1)
    autodownload = st.checkbox("Enable autodownload of attached files", value=False)
    language = st.selectbox("Select Language", options=["en", "zh"], index=0)

    # Button to start scraping
    if st.button("Start Scraping"):
        if url:
            with st.spinner("Scraping..."):
                try:
                    # Call the RAGAgent's process_url method to scrape content
                    # num_docs, num_downloaded_files = rag_agent.process_url(url, max_pages=max_pages, autodownload=autodownload, language=language)
                    num_docs, num_downloaded_files = data_agent.process_url(url, max_pages=max_pages, autodownload=autodownload, language=language)

                    # Display the scraping results
                    st.success(f"Scraping completed! {num_docs} pages scraped.")
                    if autodownload:
                        st.write(f"Files downloaded: {num_downloaded_files}")

                    # Display scraped URLs from the scraper
                    st.write("Scraped URLs:")
                    # for url in rag_agent.scraper.scraped_urls:
                    #     st.write(url)
                    for url in data_agent.scraper.scraped_urls:
                        st.write(url)

                except Exception as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.warning("Please enter a valid URL.")