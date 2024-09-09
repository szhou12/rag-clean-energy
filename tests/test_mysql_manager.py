import pytest
from sqlalchemy_utils import database_exists, create_database, drop_database
from datetime import datetime, timedelta
import os
from db_mysql.dom import Base, WebPage, WebPageChunk
from db_mysql import MySQLManager

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

    # Clear the tables before each test (optional)
    session.query(WebPageChunk).delete()
    session.query(WebPage).delete()
    session.commit()  # Commit deletion

    yield session
    # Rollback any further uncommitted changes (if any)
    session.rollback()
    # Close the session after each test
    mysql_manager.close_session(session)


def test_insert_web_page(mysql_manager, session):
    url = "https://example.com"
    mysql_manager.insert_web_page(session, url, refresh_freq=7)
    
    # Check if the web page was inserted
    page = session.query(WebPage).filter_by(source=url).first()
    assert page is not None
    assert page.source == url
    assert page.refresh_frequency == 7

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
        {'source': 'https://example3.com', 'refresh_freq': 5},
        {'source': 'https://example4.com', 'refresh_freq': 10},
        {'source': 'https://example5.com', 'refresh_freq': None}
    ]
    mysql_manager.insert_web_pages(session, document_info_list)
    
    # Check if the web pages were inserted
    pages = session.query(WebPage).filter(WebPage.source.in_([d['source'] for d in document_info_list])).all()
    assert len(pages) == len(document_info_list)

def test_insert_web_page_chunks(mysql_manager, session):
    """
    Test inserting web page chunks in bulk.
    """
    url = "https://example5.com"
    mysql_manager.insert_web_page(session, url)
    page = session.query(WebPage).filter_by(source=url).first()
    
    chunk_info_list = [
        {'id': 'chunk1', 'source': page.source},
        {'id': 'chunk2', 'source': page.source}
    ]
    mysql_manager.insert_web_page_chunks(session, chunk_info_list)
    
    # Check if the chunks were inserted
    chunks = session.query(WebPageChunk).filter_by(source=page.source).all()
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