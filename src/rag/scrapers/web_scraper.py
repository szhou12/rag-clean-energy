from langchain_community.document_loaders import WebBaseLoader
import os
import requests
from collections import deque
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import inspect

class WebScraper:
    def __init__(self, mysql_manager, dir=None):
        """
        Initialize the WebScraper with necessary components.
        
        :param mysql_manager: MySQLManager instance to interact with the database
        :param dir: Directory to store auto-downloaded files when scraping
        """
        # TODO: AFTER cloud deployment, use provided cloud space to temporarily stored auto-downloaded files. May use env variable to store the directory path?
        self.dir = dir or os.path.join(os.getcwd(), 'downloads')

        # Create the download directory if it does not exist yet
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)

        # Load already existing files in the download directory
        self.downloaded_files = self._load_existing_files()
        
        # Reference to MySQLManager for database interaction
        self.mysql_manager = mysql_manager
        # Fetch scraped URLs from MySQL
        self.scraped_urls = set()
        self.fetch_active_urls_from_db()

        # Internal exclusion URL keywords (private)
        self._exclude_keywords = {"about", "about-us", "contact", "contact-us", "help", "help-centre", "help-center", "career", "careers", "job", "jobs", "privacy", "terms", "policy", "faq", "support", "login", "register", "signup", "sign-up", "subscribe", "unsubscribe", "donate", "shop", "store", "cart", "checkout", "search", "events", "programmes"}
    
    def scrape(self, url: str, max_pages: int=1, autodownload: bool=False):
        """
        Scrape content from one or multiple pages starting from the given root URL.
        Use BFS to follow links to next pages.
        Enqueue Rules:
        1. only enqueuing sub-URLs/subdirectories of current URL.
        2. exclude certain pages based on internally defined keywords (self._exclude_keywords) in the path

        :param url: The root URL to start scraping from.
        :param max_pages: Maximum number of pages to scrape (default is 1).
        :param autodownload: If True, automatically download files attached to each web page.
        :return: (List[Document], List[str]) - List of Langchain Document objects loaded from the URLs, List of newly downloaded file paths in current scraping session
        """
        visited = set() # visited url in current round of scraping session
        docs = []
        pages_scraped = 0
        newly_downloaded_files = []  # Store newly downloaded files in current round of scraping session

        # Step 1: start node
        queue = deque([url])
        visited.add(url)

        # Step 2: Loop
        while queue and pages_scraped < max_pages:
            # Cur
            current_url = queue.popleft()
            # Parse the parent URL to get the base for comparison with neighbor URLs
            current_url_parsed = urlparse(current_url)
            # Update
            if current_url in self.scraped_urls: # skip if current URL is already scraped
                continue
            doc = self.load_url(current_url) # doc = List[Document] or None. one doc = one whole web page content without split
            if doc:
                docs.extend(doc)
                pages_scraped += 1

            # Handle request errors
            try:
                response = requests.get(current_url)  # get HTML content from the URL
                response.raise_for_status()  # Raise an exception for bad status codes
            except Exception as e:
                print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Request failed for {current_url}: {e}")
                continue
            soup = BeautifulSoup(response.text, 'html.parser')  # convert HTML to BeautifulSoup object

            if autodownload:
                newly_downloaded_files.extend(self._detect_and_download_files(soup, current_url))

            # Make the next move
            for link in soup.find_all('a', href=True):
                nei_url = urljoin(current_url, link['href'])
                nei_url_parsed = urlparse(nei_url)

                # check if a valid url
                if not self._is_valid_url(nei_url):
                    continue
                # check if already visited
                if nei_url in visited:
                    continue
                # check if a valid sub-URL of the current URL
                if not self._is_valid_suburl(current_url_parsed, nei_url_parsed):
                    continue
                # check if the URL should be excluded based on internal keywords
                if self._should_exclude(nei_url_parsed):
                    continue

                queue.append(nei_url)
                visited.add(nei_url)

        # docs = List[Document]
        # newly_downloaded_files = List[<str>filepath]
        return docs, newly_downloaded_files
                    

    def load_url(self, url):
        """
        Use Langchain to load the content of a web page from a given URL.
        Record the URL that's been successfully scraped by Langchain in the set
        
        :param url: URL of the web page to load
        :return: List[Document] or None if the URL has already been scraped
        NOTE: even though the return value is List[Document], since only one URL is loaded at a time, 
        the list will always have one element.
        """

        if url == "":
            return None
        
        # Load the content from the URL
        loader = WebBaseLoader(url)
        doc = loader.load()

        # ensure the source URL is set in the metadata
        if doc[0].metadata.get('source', None) is None:
            doc[0].metadata['source'] = url
        
        return doc



    def _load_existing_files(self) -> set:
        """
        Load file paths of existing files in the download directory into a set.
        """
        existing_files = set()
        for root, _, files in os.walk(self.dir):
            for file in files:
                existing_files.add(os.path.join(root, file))
        return existing_files
    
    def _download_file(self, file_url):
        """
        Private method to download a file from a given URL. To be called by _detect_and_download_files().
        Currently supports [.pdf, .xlsx, .xls] file types.

        If the target website forbids downloading files, skip it to ensure the scraper does not get blocked.
        
        :param file_url: URL of the file to download
        :return: <str> Path to the downloaded file
        """
        local_filename = os.path.join(self.dir, os.path.basename(file_url))

        # Check if file already downloaded
        if local_filename in self.downloaded_files:
            return None
        
        # Perform the request and handle errors
        try:
            with requests.get(file_url, stream=True) as r:
                r.raise_for_status()  # Raise an error for bad status codes
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            self.downloaded_files.add(local_filename)
        except Exception as e:
            print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Failed to download {file_url}: {e}")
            return None
        
        return local_filename
    
    def _detect_and_download_files(self, soup, base_url) -> list:
        """
        Private method to detect and download files attached to the web page.
        Detects [.pdf, .xlsx, .xls] file types.
        
        :param soup: BeautifulSoup object of the scraped web page
        :param base_url: The base URL to resolve relative file links. i.e. URL of the current web page where the file is attached to
        :return: List of paths to newly downloaded files in the current scraping session
        """
        newly_downloaded_files = []
        file_extensions = ['.pdf', '.xlsx', '.xls']
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            if any(href.lower().endswith(ext) for ext in file_extensions):
                file_url = urljoin(base_url, href)
                file_path = self._download_file(file_url)
                
                # Add to the list only if it was newly downloaded
                if file_path:
                    newly_downloaded_files.append(file_path)

        return newly_downloaded_files

    def _is_valid_url(self, url) -> bool:
        """
        Validate the URL to ensure it has both a scheme and network location.
        Scheme: https, http
        Network location: domain name + port name (optional). e.g. www.iea.org, www.iea.org:8080
        """
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme)
    
    def _is_valid_suburl(self, root_url_parsed, child_url_parsed) -> bool:
        """
        Validate the child URL to ensure it is a sub-URL of the root URL.
        
        :param root_url_parsed: Parsed result of the root URL provided by the user.
        :param child_url_parsed: Parsed result of the child URL connected to the root URL.
        :return: True if child_url_parsed is a valid sub-URL of root_url_parsed, False otherwise.

        Example:
        https://www.iea.org/energy-system/fossil-fuels/coal is a sub-URL of https://www.iea.org/energy-system/fossil-fuels
        Cases that are NOT sub-URLs:
        1. Do NOT have the complete root URL path
        https://www.iea.org/about is NOT a sub-URL of https://www.iea.org/energy-system/fossil-fuels
        2. Fragment identifier (path followed by # symbol):
        https://www.iea.org/energy-system/fossil-fuels#content is NOT a sub-URL of https://www.iea.org/energy-system/fossil-fuels
        "https://www.iea.org/energy-system/electricity/nuclear-power#tracking" is NOT a sub-URL of "https://www.iea.org/energy-system/electricity"
        3. Query parameters (path followed by ? symbol):
        https://www.iea.org/energy-system/fossil-fuels?ref=home is NOT a sub-URL of https://www.iea.org/energy-system/fossil-fuels
        """
        # Check that the network location (domain) matches
        if root_url_parsed.netloc != child_url_parsed.netloc:
            return False
        
        # Check that the child URL path starts with the root URL path and is longer
        # ALso, if child starts starts with root and is longer, ensure that it is not with a fragment or query
        if not child_url_parsed.path.startswith(root_url_parsed.path):
            return False
        elif child_url_parsed.fragment or child_url_parsed.query:
            return False
        
        # Ensure the child path is a true subdirectory
        if child_url_parsed.path == root_url_parsed.path:
            return False
        
        return True
    
    def _should_exclude(self, child_url_parsed) -> bool:
        """
        Check if a URL should be excluded from scraping based on the first path segment.
        Exclusion rule: exclude if the specified keyword is the first path segment.
        i.e. the exclusion keyword directly follows the domain name (netloc).
        Example:
        https://www.iea.org/about is excluded

        :param child_url_parsed: Parsed result of the child URL connected to the root URL..
        :return: True if the URL should be excluded, False otherwise.
        """
        path_segments = child_url_parsed.path.strip('/').split('/')
        return len(path_segments) > 0 and path_segments[0] in self._exclude_keywords
    
    def fetch_active_urls_from_db(self):
        """
        Reset the set of scraped URLs by fetching the latest URLs from MySQL.
        Fetch previously scraped and currently active URLs from the MySQL database.
        Returns a set of URLs.
        """
        session = self.mysql_manager.create_session()
        try:
            # Use MySQLManager to fetch all active scraped URLs from the database
            self.scraped_urls = self.mysql_manager.get_active_urls(session)
        finally:
            self.mysql_manager.close_session(session)
    
    
