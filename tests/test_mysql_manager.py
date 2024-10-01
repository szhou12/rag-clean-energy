import pytest
from sqlalchemy import delete, select
from sqlalchemy_utils import database_exists, create_database, drop_database
from datetime import datetime, timedelta
import os
from db_mysql.dao import Base, WebPage, WebPageChunk, FilePage, FilePageChunk
from db_mysql import MySQLManager
import time

# Setup test database configuration
TEST_DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': os.getenv('MYSQL_PASSWORD'),
    'port': 3306,
    'database': 'test_db'  # test database
}

@pytest.fixture(scope="module")
def mysql_manager():
    """
    This fixture sets up the MySQLManager and creates the test database
    before tests, then drops the database after all tests are done.
    """
    TEST_DB_URI = f"mysql+mysqlconnector://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}@" \
             f"{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/{TEST_DB_CONFIG['database']}"
    
    # Setup: Create the test database before running tests
    if not database_exists(TEST_DB_URI):
        create_database(TEST_DB_URI)
    
    # Create MySQLManager instance
    manager = MySQLManager(
        host=TEST_DB_CONFIG['host'],
        user=TEST_DB_CONFIG['user'],
        password=TEST_DB_CONFIG['password'],
        port=TEST_DB_CONFIG['port'],
        db_name=TEST_DB_CONFIG['database']
    )
    
    yield manager
    
    # Tear down: close connection and drop test database
    manager.close()
    drop_database(TEST_DB_URI)


@pytest.fixture(scope="function")
def session(mysql_manager):
    # Create a new session for each test
    session = mysql_manager.create_session()

    # Clear the tables before each test
    session.execute(delete(WebPage))
    session.execute(delete(WebPageChunk))
    session.execute(delete(FilePage))
    session.execute(delete(FilePageChunk))
    session.commit()  # Commit deletion

    yield session
    # Rollback any further uncommitted changes (if any)
    session.rollback()
    # Close the session after each test
    mysql_manager.close_session(session)


def test_insert_web_page(mysql_manager, session):
    url = "https://example.com"
    language = "en"
    mysql_manager.insert_web_page(session, url, refresh_freq=7, language=language)
    
    # Check if the web page was inserted
    sql_stmt = select(WebPage).filter_by(source=url)
    page = session.scalars(sql_stmt).first()
    assert page is not None
    assert page.source == url
    assert page.refresh_frequency == 7
    assert page.language == language

def test_check_web_page_exists(mysql_manager, session):
    url = "https://example2.com"
    mysql_manager.insert_web_page(session, url)
    
    # Check if the web page exists
    existing_page = mysql_manager.check_web_page_exists(session, url)
    assert existing_page is not None
    assert existing_page.source == url


def test_insert_web_pages(mysql_manager, session):
    """
    Test bulk inserting multiple web pages into the database.
    """
    document_info_list = [
        {'source': 'https://example3.com', 'refresh_freq': 5, 'language': 'en'},
        {'source': 'https://example4.com', 'refresh_freq': 10, 'language': 'zh'},
        {'source': 'https://example5.com', 'refresh_freq': None, 'language': 'en'}
    ]
    mysql_manager.insert_web_pages(session, document_info_list)
    
    # Check if the web pages were inserted
    sql_stmt = select(WebPage).filter(WebPage.source.in_([d['source'] for d in document_info_list]))
    pages = session.scalars(sql_stmt).all()
    assert len(pages) == len(document_info_list)

    # Check the language for each page
    for i, page in enumerate(pages):
        assert page.language == document_info_list[i]['language']

def test_insert_web_page_chunks(mysql_manager, session):
    """
    Test inserting web page chunks in bulk.
    """
    url = "https://example5.com"
    mysql_manager.insert_web_page(session, url)
    sql_stmt = select(WebPage).filter_by(source=url)
    page = session.scalars(sql_stmt).first()
    
    chunk_info_list = [
        {'id': 'chunk1', 'source': page.source},
        {'id': 'chunk2', 'source': page.source}
    ]
    mysql_manager.insert_web_page_chunks(session, chunk_info_list)
    
    # Check if the chunks were inserted
    sql_stmt = select(WebPageChunk).filter_by(source=page.source)
    chunks = session.scalars(sql_stmt).all()
    assert len(chunks) == len(chunk_info_list)


def test_get_all_urls(mysql_manager, session):
    urls = ["https://example6.com", "https://example7.com"]
    for url in urls:
        mysql_manager.insert_web_page(session, url)
    
    all_urls = mysql_manager.get_all_urls(session)
    assert set(urls).issubset(all_urls)

def test_get_active_urls(mysql_manager, session):
    # Insert a page that doesn't need refresh
    mysql_manager.insert_web_page(session, "https://example8.com", refresh_freq=None)
    
    # Insert a page that needs refresh
    page = WebPage(source="https://example9.com", freq=1)
    page.date = datetime.now() - timedelta(days=2)  # Set last scraped date to 2 days ago
    session.add(page)
    session.commit()
    
    active_urls = mysql_manager.get_active_urls(session)
    assert "https://example8.com" in active_urls
    assert "https://example9.com" not in active_urls


def test_get_active_urls_no_web_pages(mysql_manager, session):
    """
    Test get_active_urls method to ensure it returns an empty set if no web pages exist.
    """
    # Case 1: No web pages in the database
    active_urls = mysql_manager.get_active_urls(session)
    
    # Check that the returned data type is a set
    assert isinstance(active_urls, set), f"Expected 'set', but got {type(active_urls)}"
    # Check that the length of the set is 0
    assert len(active_urls) == 0, f"Expected 0 active URLs, but got {len(active_urls)}"

def test_get_active_urls_no_refresh_needed(mysql_manager, session):
    """
    Test get_active_urls method to ensure it returns all urls if no web pages need a refresh.
    """
    # Insert web pages that do not need a refresh
    web_pages_metadata = [
        {'source': 'https://example1.com', 'refresh_freq': None},  # No refresh frequency
        {'source': 'https://example2.com', 'refresh_freq': 10}  # Refresh not due
    ]
    
    # Insert web pages into the database
    mysql_manager.insert_web_pages(session, web_pages_metadata)
    
    # Ensure the web pages do not need refresh immediately
    active_urls = mysql_manager.get_active_urls(session)

    # Check that the returned data type is a set
    assert isinstance(active_urls, set), f"Expected 'set', but got {type(active_urls)}"
    # Check that the length of the set is 0
    assert len(active_urls) == len(web_pages_metadata), f"Expected 0 active URLs, but got {len(active_urls)}"

def test_get_web_page_chunk_ids_by_single_source(mysql_manager, session):
    """
    Test get_web_page_chunk_ids_by_single_source method to ensure it correctly fetches chunk IDs 
    for the given source URL.
    """
    # Step 1: Insert a web page and its associated chunks into the database.
    source_url = "https://example.com"
    
    # Insert the web page
    mysql_manager.insert_web_page(session, source_url, refresh_freq=None)

    # Query to get the web page
    sql_stmt = select(WebPage).filter_by(source=source_url)
    web_page = session.scalars(sql_stmt).first()

    # Ensure web page was added correctly
    assert web_page is not None
    assert web_page.source == source_url
    
    # Insert chunks associated with this web page
    chunk_ids = ['chunk1', 'chunk2', 'chunk3']
    chunk_info_list = [{'id': chunk_id, 'source': source_url} for chunk_id in chunk_ids]
    mysql_manager.insert_web_page_chunks(session, chunk_info_list)

    # Step 2: Fetch chunk IDs by source URL
    fetched_chunk_ids = mysql_manager.get_web_page_chunk_ids_by_single_source(session, source_url)

    # Step 3: Verify the fetched chunk IDs match the inserted chunk IDs
    assert isinstance(fetched_chunk_ids, list)  # Ensure the return type is a list
    assert len(fetched_chunk_ids) == len(chunk_ids)  # Ensure the count matches
    assert set(fetched_chunk_ids) == set(chunk_ids)  # Ensure the IDs match


def test_get_web_page_chunk_ids_by_sources(mysql_manager, session):
    """
    Test get_web_page_chunk_ids_by_sources method to ensure it correctly fetches chunk IDs 
    for the given list of source URLs.
    """
    # Step 1: Insert multiple web pages and their associated chunks into the database
    sources = ["https://example-source-1.com", "https://example-source-2.com", "https://example-source-3.com"]

    # Insert the web pages
    web_pages_metadata = [
        {'source': sources[0], 'refresh_freq': 5},
        {'source': sources[1], 'refresh_freq': 6},
        {'source': sources[2], 'refresh_freq': 7},
    ]
    mysql_manager.insert_web_pages(session, web_pages_metadata)

    # Insert chunks associated with these web pages
    chunk_ids_for_source1 = ['chunk1', 'chunk2']
    chunk_ids_for_source2 = ['chunk3', 'chunk4']
    chunk_ids_for_source3 = ['chunk5', 'chunk6']

    chunk_info_list = [
        {'id': chunk_id, 'source': sources[0]} for chunk_id in chunk_ids_for_source1
    ] + [
        {'id': chunk_id, 'source': sources[1]} for chunk_id in chunk_ids_for_source2
    ] + [
        {'id': chunk_id, 'source': sources[2]} for chunk_id in chunk_ids_for_source3
    ]
    mysql_manager.insert_web_page_chunks(session, chunk_info_list)

    # Step 2: Fetch chunk IDs by list of source URLs
    fetched_chunk_ids = mysql_manager.get_web_page_chunk_ids_by_sources(session, sources)

    # Step 3: Verify the fetched chunk IDs match the inserted chunk IDs
    all_chunk_ids = chunk_ids_for_source1 + chunk_ids_for_source2 + chunk_ids_for_source3

    assert isinstance(fetched_chunk_ids, list), "Expected 'list' but got {type(fetched_chunk_ids)}"
    assert len(fetched_chunk_ids) == len(all_chunk_ids), f"Expected {len(all_chunk_ids)} chunk IDs, but got {len(fetched_chunk_ids)}"
    assert set(fetched_chunk_ids) == set(all_chunk_ids), "Fetched chunk IDs do not match the expected IDs"

def test_update_single_web_page_date(mysql_manager, session):
    """
    Test the update_single_web_page_date method to ensure it correctly resets the date
    for a specific web page URL.
    """
    url = "https://example-single-update.com"
    
    # Insert the web page
    mysql_manager.insert_web_page(session, url, refresh_freq=None)

    # Query to get the initial web page details
    sql_stmt = select(WebPage).filter_by(source=url)
    web_page = session.scalars(sql_stmt).first()

    # Ensure web page was added correctly
    assert web_page is not None
    old_date = web_page.date

    # Add a small delay to ensure the date change
    time.sleep(1)  # 1 second delay

    # Update the date of the single web page
    mysql_manager.update_single_web_page_date(session, url)

    # Fetch the updated web page details
    web_page_updated = session.scalars(sql_stmt).first()

    # Ensure the date has been updated
    assert web_page_updated.date > old_date, "The date was not updated correctly."


def test_update_web_pages_date(mysql_manager, session):
    """
    Test that multiple web pages' dates are updated correctly.
    """
    urls = ["https://example11.com", "https://example12.com"]
    
    # Insert the web pages
    for url in urls:
        mysql_manager.insert_web_page(session, url, refresh_freq=7)
    
    # Get the inserted web pages and check the dates
    sql_stmt = select(WebPage).filter(WebPage.source.in_(urls))
    pages = session.scalars(sql_stmt).all()
    old_dates = [page.date for page in pages]

    # Add a small delay to ensure the date change
    time.sleep(1)  # 1 second delay
    
    # Call the method to update the pages' dates
    mysql_manager.update_web_pages_date(session, urls)
    
    # Fetch the updated pages and check if the dates were updated
    pages = session.scalars(sql_stmt).all()
    for i, page in enumerate(pages):
        assert page.date > old_dates[i], f"The date for {page.source} should be updated."


def test_delete_web_page_chunks_by_ids(mysql_manager, session):
    """
    Test that web page chunks are deleted correctly by chunk IDs.
    """
    url = "https://example-delete-web-page.com"
    
    # Insert the web page
    mysql_manager.insert_web_page(session, url, refresh_freq=7)
    
    # Insert some chunks associated with the web page
    chunk_info_list = [{'id': '0001', 'source': url}, {'id': '0002', 'source': url}]
    mysql_manager.insert_web_page_chunks(session, chunk_info_list)
    
    # Confirm the chunks were inserted
    sql_stmt = select(WebPageChunk).filter_by(source=url)
    chunks = session.scalars(sql_stmt).all()
    assert len(chunks) == len(chunk_info_list), "WebPageChunks are not correctly inserted."
    
    # Delete the chunks by IDs
    chunk_ids = ['0001', '0002']
    mysql_manager.delete_web_page_chunks_by_ids(session, chunk_ids)
    
    # Confirm the chunks were deleted
    chunks = session.scalars(sql_stmt).all()
    assert len(chunks) == 0, "WebPageChunks are not correctly deleted."


def test_insert_web_pages_no_commit(mysql_manager, session):
    """
    Test inserting multiple web pages without committing the session to ensure rollback works.
    """
    url = "https://example14.com"
    document_info = [{'source': url, 'refresh_freq': 7}]
    
    # Insert a web page
    mysql_manager.insert_web_pages(session, document_info)
    
    # Rollback the session without committing
    session.rollback()
    
    # Check that the web page was not inserted
    sql_stmt = select(WebPage).filter_by(source=url)
    page = session.scalars(sql_stmt).first()
    assert page is None, "The web page should not be inserted after a rollback."

def test_delete_web_pages_by_sources(mysql_manager, session):
    """
    Test deleting web pages by a list of source URLs.
    """
    # Step 1: Insert web pages into the database
    web_pages_metadata = [
        {'source': 'https://example-delete-10.com', 'refresh_freq': 7},
        {'source': 'https://example-delete-11.com', 'refresh_freq': 10},
        {'source': 'https://example-delete-12.com', 'refresh_freq': None}
    ]
    
    mysql_manager.insert_web_pages(session, web_pages_metadata)
    
    # Verify that the web pages were inserted
    sql_stmt = select(WebPage).filter(WebPage.source.in_([d['source'] for d in web_pages_metadata]))
    inserted_pages = session.scalars(sql_stmt).all()
    assert len(inserted_pages) == len(web_pages_metadata)
    
    # Step 2: Delete some of the web pages
    sources_to_delete = ['https://example-delete-10.com', 'https://example-delete-12.com']
    mysql_manager.delete_web_pages_by_sources(session, sources_to_delete)
    
    # Commit the changes
    session.commit()
    
    # Step 3: Verify that the web pages were deleted
    remaining_pages_sql_stmt = select(WebPage).filter(WebPage.source.in_(sources_to_delete))
    remaining_pages = session.scalars(remaining_pages_sql_stmt).all()
    assert len(remaining_pages) == 0  # These should have been deleted
    
    # Verify that the non-deleted page is still present
    still_exists_sql_stmt = select(WebPage).filter(WebPage.source == 'https://example-delete-11.com')
    still_exists_page = session.scalars(still_exists_sql_stmt).first()
    assert still_exists_page is not None
    assert still_exists_page.source == 'https://example-delete-11.com'

def test_get_web_page_language_by_single_source(mysql_manager, session):
    """
    Test fetching the language of a single web page by its source URL.
    """
    # Insert a test web page into the database
    url = "https://example-en.com"
    language = "zh"
    mysql_manager.insert_web_page(session, url, refresh_freq=23, language=language)
    
    # Retrieve the language using the get_web_page_language_by_single_source method
    retrieved_language = mysql_manager.get_web_page_language_by_single_source(session, url)
    
    # Assert that the returned language matches the expected value
    assert retrieved_language == language, f"Expected {language} but got {retrieved_language}"

def test_get_web_page_language_by_single_source_nonexistent(mysql_manager, session):
    """
    Test fetching the language of a non-existent source URL.
    """
    # Attempt to get the language for a URL that does not exist
    nonexistent_url = "https://nonexistent.com"
    retrieved_language = mysql_manager.get_web_page_language_by_single_source(session, nonexistent_url)
    
    # Assert that the returned value is None
    assert retrieved_language is None, "Expected None for non-existent URL"

def test_get_web_page_languages_by_sources(mysql_manager, session):
    """
    Test fetching the languages for multiple web pages by their source URLs and grouping them by 'en' and 'zh'.
    """
    # Insert multiple test web pages with different languages
    pages_metadata = [
        {"source": "https://example-en-1.com", "language": "en"},
        {"source": "https://example-zh-2.com", "language": "zh"},
        {"source": "https://example-en-3.com", "language": "en"},
    ]
    for page in pages_metadata:
        mysql_manager.insert_web_page(session, page["source"], refresh_freq=7, language=page["language"])
    
    # Retrieve the languages using the get_languages_by_sources method
    sources = ["https://example-en-1.com", "https://example-zh-2.com", "https://example-en-3.com"]
    retrieved_languages = mysql_manager.get_web_page_languages_by_sources(session, sources)
    
    # Assert that the returned dictionary contains the correct grouping of sources by language
    expected_languages = {
        "en": ["https://example-en-1.com", "https://example-en-3.com"],
        "zh": ["https://example-zh-2.com"],
    }
    assert retrieved_languages == expected_languages, f"Expected {expected_languages} but got {retrieved_languages}"

def test_get_web_page_languages_by_sources_partial_existence(mysql_manager, session):
    """
    Test fetching languages when some URLs exist and some don't, and grouping the existing ones by 'en' and 'zh'.
    """
    # Insert some test web pages
    pages_metadata = [
        {"source": "https://example1.com", "language": "en"},
        {"source": "https://example2.com", "language": "zh"},
    ]
    for page in pages_metadata:
        mysql_manager.insert_web_page(session, page["source"], refresh_freq=7, language=page["language"])
    
    # Retrieve the languages for both existing and non-existent URLs
    sources = ["https://example1.com", "https://example2.com", "https://nonexistent.com"]
    retrieved_languages = mysql_manager.get_web_page_languages_by_sources(session, sources)
    
    # Assert that only the existing URLs are returned and grouped correctly
    expected_languages = {
        "en": ["https://example1.com"],
        "zh": ["https://example2.com"],
    }
    assert retrieved_languages == expected_languages, f"Expected {expected_languages} but got {retrieved_languages}"

def test_insert_file_pages(mysql_manager, session):
    """
    Test inserting multiple file pages into the database.
    """
    file_pages = [
        {'source': 'example1.pdf', 'page': '1', 'language': 'en'},
        {'source': 'example2.xlsx', 'page': 'Sheet1', 'language': 'zh'},
        {'source': 'example1.pdf', 'page': '2', 'language': 'en'}
    ]
    
    # Insert file pages
    mysql_manager.insert_file_pages(session, file_pages)

    # Verify that the file pages were inserted
    sql_stmt = select(FilePage).filter(FilePage.source.in_([f['source'] for f in file_pages]))
    inserted_file_pages = session.scalars(sql_stmt).all()
    
    assert len(inserted_file_pages) == len(file_pages)

    # Create sets of tuples for comparison
    expected_set = set((fp['source'], fp['page'], fp['language']) for fp in file_pages)
    actual_set = set((fp.source, fp.page, fp.language) for fp in inserted_file_pages)

    assert expected_set == actual_set, f"Mismatch in inserted data. Expected: {expected_set}, Got: {actual_set}"

    # Optional: Check if 'date' was set for each inserted page
    for page in inserted_file_pages:
        assert page.date is not None, f"Date not set for page: {page}"


def test_insert_file_page_chunks(mysql_manager, session):
    """
    Test inserting file page chunks in batch.
    """
    file_pages = [
        {'source': 'example3.pdf', 'page': '1', 'language': 'en'},
    ]
    mysql_manager.insert_file_pages(session, file_pages)

    sql_stmt = select(FilePage).filter_by(source=file_pages[0]['source'], page=file_pages[0]['page'])
    file_page = session.scalars(sql_stmt).first()
    
    chunk_info_list = [
        {'id': 'chunk1', 'source': file_page.source, 'page': file_page.page},
        {'id': 'chunk2', 'source': file_page.source, 'page': file_page.page}
    ]
    mysql_manager.insert_file_page_chunks(session, chunk_info_list)

    # Verify that the chunks were inserted
    sql_stmt = select(FilePageChunk).filter_by(source=file_page.source, page=file_page.page)
    inserted_chunks = session.scalars(sql_stmt).all()
    
    assert len(inserted_chunks) == len(chunk_info_list)


def test_get_file_page_chunk_ids(mysql_manager, session):
    """
    Test fetching file page chunk IDs based on source and page.
    """
    file_pages = [
        {'source': 'example4.pdf', 'page': '1', 'language': 'en'},
        {'source': 'example4.pdf', 'page': '2', 'language': 'en'}
    ]
    mysql_manager.insert_file_pages(session, file_pages)

    chunk_info_list = [
        {'id': 'chunk1', 'source': 'example4.pdf', 'page': '1'},
        {'id': 'chunk2', 'source': 'example4.pdf', 'page': '2'}
    ]
    mysql_manager.insert_file_page_chunks(session, chunk_info_list)

    # Test fetching chunks based on source and page
    sources_and_pages = [{'source': 'example4.pdf', 'page': '1'}, {'source': 'example4.pdf', 'page': '2'}]
    chunk_ids = mysql_manager.get_file_page_chunk_ids(session, sources_and_pages)

    assert set(chunk_ids) == {'chunk1', 'chunk2'}


def test_delete_file_pages_by_sources_and_pages(mysql_manager, session):
    """
    Test deleting file pages by source and page.
    """
    file_pages = [
        {'source': 'example5.pdf', 'page': '1', 'language': 'en'},
        {'source': 'example5.pdf', 'page': '2', 'language': 'en'},
        {'source': 'example6.pdf', 'page': '1', 'language': 'zh'}
    ]
    mysql_manager.insert_file_pages(session, file_pages)

    # Verify the pages were inserted
    sql_stmt = select(FilePage).filter(FilePage.source.in_(['example5.pdf', 'example6.pdf']))
    inserted_pages = session.scalars(sql_stmt).all()
    assert len(inserted_pages) == len(file_pages)

    # Delete some file pages
    sources_and_pages = [{'source': 'example5.pdf', 'page': '1'}, {'source': 'example6.pdf', 'page': '1'}]
    mysql_manager.delete_file_pages_by_sources_and_pages(session, sources_and_pages)

    # Verify that the pages were deleted
    remaining_pages_sql_stmt = select(FilePage).filter(
        FilePage.source == 'example5.pdf',
        FilePage.page == '2'
    )
    remaining_page = session.scalars(remaining_pages_sql_stmt).first()
    assert remaining_page is not None

    deleted_pages_sql_stmt = select(FilePage).filter(
        FilePage.source.in_(['example5.pdf', 'example6.pdf']),
        FilePage.page.in_(['1'])
    )
    deleted_pages = session.scalars(deleted_pages_sql_stmt).all()
    assert len(deleted_pages) == 0


def test_delete_file_page_chunks_by_ids(mysql_manager, session):
    """
    Test deleting file page chunks by chunk IDs.
    """
    file_pages = [
        {'source': 'example7.pdf', 'page': '1', 'language': 'en'},
    ]
    mysql_manager.insert_file_pages(session, file_pages)

    chunk_info_list = [
        {'id': 'chunk1', 'source': 'example7.pdf', 'page': '1'},
        {'id': 'chunk2', 'source': 'example7.pdf', 'page': '1'}
    ]
    mysql_manager.insert_file_page_chunks(session, chunk_info_list)

    # Verify that the chunks were inserted
    sql_stmt = select(FilePageChunk).filter_by(source='example7.pdf', page='1')
    inserted_chunks = session.scalars(sql_stmt).all()
    assert len(inserted_chunks) == len(chunk_info_list)

    # Delete the chunks by their IDs
    chunk_ids = ['chunk1', 'chunk2']
    mysql_manager.delete_file_page_chunks_by_ids(session, chunk_ids)

    # Verify that the chunks were deleted
    remaining_chunks = session.scalars(sql_stmt).all()
    assert len(remaining_chunks) == 0