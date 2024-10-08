import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from db_mysql import MySQLManager
from rag import RAGAgent

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


rag_agent = RAGAgent(mysql_config=mysql_config, vector_db="db_chroma")
data = rag_agent.get_file_metadata()


# Function to extract file name from the full path
def get_filename_from_path(filepath):
    return os.path.basename(filepath)

# Set up the Streamlit page
st.set_page_config(page_title="Data Table", layout="wide")

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
        "source": "File Name"  # Rename 'source' column to 'File Name'
    },
    disabled=["id", "source", "page", "date", "language"],  # Disable editing on these columns
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

# Optional: Add a filter for the 'page' column
# page_filter = st.selectbox("Filter by page", options=["All"] + list(st.session_state.df['page'].unique()))
# if page_filter != "All":
#     filtered_df = st.session_state.df[st.session_state.df['page'] == page_filter]
#     st.dataframe(filtered_df)


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
        rag_agent.process_file(file_path)