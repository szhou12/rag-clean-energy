# helper functions for Streamlit pages
import os
from collections import defaultdict
import pandas as pd

def clean_web_data(web_data: list[dict]):
    """
    Clean web page metadata fetched from the database.

    :param web_data: List of dictionaries. Example: [{'id': 1, 'url': 'https://example.com', 'date': '2024-10-08', 'language': 'en'}, ...]
    :return: Pandas DataFrame containing cleaned data.
    """
    if web_data:
        # Prepare the data: Exclude 'id' field from display
        for row in web_data:
            del row['id']
        return pd.DataFrame(web_data)
    return pd.DataFrame()  # Return an empty DataFrame if no data found

def group_files_by_source(file_data: list[dict]):
    """
    Group file data by their source and return file-level information without individual pages.

    :param file_data: List of dictionaries. Example: [{'id': 1, 'source': 'path1/to/manufacturing.pdf', 'page': '1', 'date': '2024-10-08', 'language': 'en'}, ...]
    :return: List of dictionaries, each representing file-level information.
    """

    # Group pages by file source
    files_grouped = defaultdict(list)
    for file in file_data:
        files_grouped[file['source']].append(file)

    # Create file-level data (without pages)
    file_info = []
    for source, pages in files_grouped.items():
        # Use only the file-level info, display only the filename (not the full path)
        file_info.append({
            'source': os.path.basename(source),  # Just display filename
            'total_pages': len(pages),
            'date': pages[0]['date'],  # Assuming all pages have the same date
            'language': pages[0]['language'],  # Assuming all pages have the same language
            'Delete': False  # Add a Delete column for the table
        })
    
    return file_info


def reformat_del_data(rows_to_delete, file_name_to_full_path, file_data):
    """
    Process the deletions by recovering full paths and grouping the selected rows by language.

    :param rows_to_delete: DataFrame containing rows marked for deletion, with 'source' column.
    :param file_name_to_full_path: Dictionary mapping file names to their full paths.
    :param file_data: List of dictionaries, each representing a file's metadata including 'source', 'language', etc.
    :return: Dictionary with language keys ('en', 'zh') and a list of corresponding file rows.
    """
    # Get list of sources (file names) to delete
    sources_to_delete = rows_to_delete['source'].tolist()

    # Recover the full paths using the file_name_to_full_path mapping
    full_paths_to_delete = [file_name_to_full_path[source] for source in sources_to_delete]

    # Find the corresponding rows in the original file_data based on full paths
    selected_rows = [row for row in file_data if row['source'] in full_paths_to_delete]

    # Group the selected rows by language
    reformatted_data = {"en": [], "zh": []}
    for row in selected_rows:
        if row['language'] in reformatted_data:
            reformatted_data[row['language']].append(row)

    return reformatted_data