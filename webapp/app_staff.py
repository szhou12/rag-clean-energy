import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from rag import DataAgent
from utils import group_files_by_source, reformat_del_data, clean_web_data

load_dotenv()


# NOTE: client_staff is also running in a docker container. Inside Docker, the containers use their internal ports to communicate
mysql_config = {
        'user': 'root',
        'host': 'mysql_container', # Docker service name of the MySQL container
        'port': 3306,               # Use the internal MySQL port inside the container
        'password': os.getenv('MYSQL_ROOT_PASSWORD'),
        'db_name': 'rmi_test'
    }


# Initialize DataAgent
data_agent = DataAgent(mysql_config=mysql_config, vector_db_persist_dir="/data/chroma")


# Set up the Streamlit page
st.set_page_config(page_title="Data Table", layout="wide")

# Create tabs
tab1, tab2 = st.tabs(["Web", "File"])


# Initialize or update web_df in session state
if 'web_df' not in st.session_state or st.session_state.get('refresh_web_data'):
    st.session_state.web_df = clean_web_data(data_agent.get_web_page_metadata())
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
                    st.session_state.web_df = clean_web_data(data_agent.get_web_page_metadata())
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
            "date": "Date",
            "language": "Language",
            "refresh_frequency": st.column_config.NumberColumn(
                "Refresh Frequency", min_value=1, help="Frequency in days"
            )
        },
        disabled=["source", "date", "language"],  # Disable editing for these columns
        key="web_data_editor",
    )

    # Create columns to arrange buttons side by side
    col1, col2, _ = st.columns([1, 1, 8])

    # Update Button: Handle frequency updates
    with col1:
        if st.button("Update"):
            # Collect rows with changed refresh frequency
            changed_frequency_rows = edited_web_df[edited_web_df['refresh_frequency'] != st.session_state.web_df['refresh_frequency']]

            if not changed_frequency_rows.empty:
                # Prepare data for updating refresh frequency
                sources_to_update_freq = changed_frequency_rows[['source', 'refresh_frequency']].to_dict(orient='records')

                try:
                    with st.spinner("Updating refresh frequency..."):
                        # Update the refresh frequency in the data agent
                        data_agent.update_web_data_refresh_frequency(sources_to_update_freq)
                        st.success("Refresh frequency has been updated.")

                    # Update the DataFrame in session state to reflect changes
                    st.session_state.web_df = clean_web_data(data_agent.get_web_page_metadata())
                    st.rerun()  # Re-run to reflect changes

                except Exception as e:
                    st.error(f"An error occurred during frequency update: {e}")
            else:
                st.warning("No frequency changes detected.")
    with col2:
        # Delete Button: Handle deletion of selected rows
        if st.button("Delete", key="delete_button", type="primary"):
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

                    # Update the DataFrame in session state to reflect changes
                    st.session_state.web_df = clean_web_data(data_agent.get_web_page_metadata())
                    st.rerun()  # Re-run to reflect changes

                except Exception as e:
                    st.error(f"An error occurred during deletion: {e}")
            else:
                st.warning("No rows selected for deletion.")




with tab2:
    ############# File upload section #############
    st.title("File Uploading")

    # Language selection
    language = st.radio("Select the language of the file:", options=["en", "zh"], index=0)

    uploaded_file = st.file_uploader("Upload a File", type=["pdf", "xlsx", "xls"])
    if uploaded_file:
        temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')
        file_path = os.path.join(temp_dir, uploaded_file.name)

        if not os.path.exists(file_path):
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            st.write(f"Saved to filepath: {file_path}")

        try:
            data_agent.process_file(file_path, language=language)
            st.success(f"File uploaded and processed successfully! Refresh to see the change!")

        except Exception as e:
            st.error(f"Error processing file: {e}")

    ############# Display data table #############
    st.title("Table for Uploaded Files")

    # Retrieve and modify data
    # file_data = data_agent.get_file_metadata()
    file_data = data_agent.get_file_page_metadata()
    # Create a mapping of file names to their full paths
    file_name_to_full_path = {os.path.basename(file['source']): file['source'] for file in file_data}

    file_info = group_files_by_source(file_data)

    # Initialize the DataFrame in session state if it doesn't already exist
    if 'file_df' not in st.session_state:
        st.session_state.file_df = pd.DataFrame(file_info)

    # Create a copy of the DataFrame for display
    display_file_df = st.session_state.file_df.copy()

    # Display editable table at the file source level
    edited_file_df = st.data_editor(
        display_file_df,
        hide_index=True,
        column_config={
            "Delete": st.column_config.CheckboxColumn(
                "Delete", help="Select to delete", default=False
            ),
            "source": "File Name",  # Rename 'source' column
            "total_pages": "Total Pages/Sheets",
            "date": "Upload Date",
            "language": "Language"
        },
        disabled=["source", "total_pages", "date", "language"],  # Disable editing for these columns
    )

    # Handle deletions
    if st.button("Submit Changes"):
        # Collect the rows marked for deletion
        rows_to_delete = edited_file_df[edited_file_df['Delete']]

        if not rows_to_delete.empty:
            del_data = reformat_del_data(rows_to_delete, file_name_to_full_path, file_data)
            try:
                with st.spinner("Deleting selected files..."):
                    # Delete the selected data
                    data_agent.delete_file_data(del_data)
                    st.success("Selected files have been deleted.")

                # Update session_state DataFrame by keeping only non-deleted rows
                st.session_state.file_df = edited_file_df[~edited_file_df['Delete']].drop(columns=['Delete']).reset_index(drop=True)

                st.rerun()  # Re-run to reflect changes

            except Exception as e:
                st.error(f"An error occurred during deletion: {e}")
        else:
            st.warning("No rows selected for deletion.")