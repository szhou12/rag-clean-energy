import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
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


# Initialize DataAgent
data_agent = DataAgent(mysql_config=mysql_config, vector_db="db_chroma")


# Set up the Streamlit page
st.set_page_config(page_title="Data Table", layout="wide")

# Create tabs
tab1, tab2 = st.tabs(["Web", "File"])

def load_web_data():
    """Fetch web page metadata from the database."""
    web_data = data_agent.get_web_page_metadata()
    if web_data:
        # Prepare the data: Exclude 'id' field from display
        for row in web_data:
            del row['id']
        return pd.DataFrame(web_data)
    return pd.DataFrame()  # Return an empty DataFrame if no data found

# Initialize or update web_df in session state
if 'web_df' not in st.session_state or st.session_state.get('refresh_web_data'):
    st.session_state.web_df = load_web_data()
    st.session_state.refresh_web_data = False  # Reset the flag

with tab1:
    st.title("Web Page Scraping")

    # URL input for scraping
    url = st.text_input("Website URL")
    max_pages = st.number_input("Maximum number of pages to scrape (max 10 pages):", min_value=1, max_value=10, value=1)
    autodownload = st.checkbox("Enable autodownload of attached files", value=False)
    language = st.selectbox("Select Language", options=["en", "zh"], index=0)

    # Button to start scraping
    if st.button("Start Scraping"):
        if url:
            with st.spinner("Scraping..."):
                try:
                    # Scrape the provided URL
                    num_docs, num_downloaded_files = data_agent.process_url(
                        url, max_pages=max_pages, autodownload=autodownload, language=language
                    )

                    # Display results
                    st.success(f"Scraping completed! {num_docs} pages scraped.")
                    if autodownload:
                        st.write(f"Files downloaded: {num_downloaded_files}")

                    # Update the DataFrame in session state
                    st.session_state.web_df = load_web_data()
                    st.rerun()  # Re-run to reflect changes

                except Exception as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.warning("Please enter a valid URL.")

    ############# Display Data Table #############
    st.title("Table for Scraped Web Pages")

    # Create a copy of the DataFrame for display
    display_web_df = st.session_state.web_df.copy()

    # Add a "Delete" column with checkboxes for deletion
    display_web_df['Delete'] = False

    # Display the data as an editable table
    edited_web_df = st.data_editor(
        display_web_df,
        hide_index=True,
        column_config={
            "Delete": st.column_config.CheckboxColumn(
                "Delete", help="Select to delete", default=False
            ),
            "source": "Source (URL)",  # Rename 'source' column for display
            "refresh_frequency": st.column_config.NumberColumn(
                "Refresh Frequency", min_value=0, help="Frequency in days"
            )
        },
        disabled=["source", "date", "language"],  # Disable editing for these columns
        key="web_data_editor",
    )

    # Button to submit changes (deletion of selected rows)
    if st.button("Submit Changes to Web Pages"):
        # Collect rows marked for deletion
        rows_to_delete = edited_web_df[edited_web_df['Delete']]

        if not rows_to_delete.empty:
            # Extract sources and languages for deletion
            sources_to_delete = rows_to_delete[['source', 'language']].to_dict(orient='records')

            try:
                with st.spinner("Deleting selected web pages..."):
                    # Delete the selected data
                    data_agent.delete_web_data(metadata=sources_to_delete)
                    st.success("Selected web pages have been deleted.")

                # Update the DataFrame in session state
                st.session_state.web_df = load_web_data()
                st.rerun()  # Re-run to reflect changes

            except Exception as e:
                st.error(f"An error occurred during deletion: {e}")
        else:
            st.warning("No rows selected for deletion.")




with tab2:
    ############# File upload section #############
    st.title("File Uploading")

    uploaded_file = st.file_uploader("Upload a File", type=["pdf", "xlsx", "xls"])
    if uploaded_file:
        temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')
        file_path = os.path.join(temp_dir, uploaded_file.name)

        if not os.path.exists(file_path):
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            st.write(f"Saved to filepath: {file_path}")

        try:
            data_agent.process_file(file_path)
            st.success(f"File uploaded and processed successfully!")
        except Exception as e:
            st.error(f"Error processing file: {e}")

    ############# Display data table #############
    st.title("Table for Uploaded Files")

    # Retrieve and modify data
    file_data = data_agent.get_file_metadata()
    for row in file_data:
        row['source'] = os.path.basename(row['source'])  # Extract filename
    
    # Initialize DataFrame in session state
    if 'file_df' not in st.session_state:
        st.session_state.file_df = pd.DataFrame(file_data)

    # Create a copy of the DataFrame for display
    display_df = st.session_state.file_df.copy()
    display_df['Delete'] = False  # Add a default "Delete" column

    # Display editable table
    edited_df = st.data_editor(
        display_df,
        hide_index=True,
        column_config={
            "Delete": st.column_config.CheckboxColumn(
                "Delete", help="Select to delete", default=False
            ),
            "source": "File Name",  # Rename 'source' column
            "total_records": "Total Pages/Sheets"
        },
        disabled=["source", "date", "language", "total_records"],
        key="data_editor",
    )

    # Delete selected rows
    if st.button("Submit Changes to Files"):
        rows_to_keep = edited_df[~edited_df['Delete']]
        st.session_state.file_df = rows_to_keep.drop(columns=['Delete']).reset_index(drop=True)
        st.success("Selected rows have been deleted.")
        st.rerun()