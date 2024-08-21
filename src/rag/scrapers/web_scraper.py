from langchain.document_loaders import WebBaseLoader
import os
import requests
from collections import deque
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

class WebScraper:
    def __init__(self, dir=None):
        # self.url = url
        # TODO: AFTER setup databse, use env variable to store the directory path
        self.dir = dir or os.path.join(os.path.dirname(__file__), '..', '..', '..', 'downloads')

        # Create the download directory if it does not exist yet
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)

        # Load already existing files in the download directory
        self.downloaded_files = self._load_existing_files()

        # File to store scraped URLs
        # TODO: configure text file path after setup database
        self.scraped_urls_file = os.path.join(os.path.dirname(__file__), "scraped_urls.txt")
        self.scraped_urls = self._load_scraped_urls()
    
    def scrape(self, url, max_pages=1, autodownload=False):
        """
        Scrape content from one or multiple pages starting from the given URL.
        Uses BFS to follow links to next pages.

        :param url: The URL to start scraping from.
        :param max_pages: Maximum number of pages to scrape (default is 1).
        :param autodownload: If True, automatically download files attached to each web page.
        :return: List of documents loaded from the URLs, List of newly downloaded file paths in current scraping session
        """
        visited = set() # visited url in current round of scraping session
        documents = []
        pages_scraped = 0
        newly_downloaded_files = []  # Store newly downloaded files in current round of scraping session

        # Step 1: start node
        queue = deque([url])
        visited.add(url)

        # Step 2: Loop
        while queue and pages_scraped < max_pages:
            # Cur
            current_url = queue.popleft()
            # Update
            doc = self._langchain_load_url(current_url) # doc := List[Document]. one doc = one whole web page content without split
            if doc:
                documents.append(doc) # documents = [ List[Document], List[Document], ...]
                pages_scraped += 1

            # Handle request errors
            try:
                response = requests.get(current_url)  # get HTML content from the URL
                response.raise_for_status()  # Raise an exception for bad status codes
            except requests.exceptions.RequestException as e:
                print(f"Request failed for {current_url}: {e}")
                continue
            soup = BeautifulSoup(response.text, 'html.parser')  # convert HTML to BeautifulSoup object

            if autodownload:
                newly_downloaded_files.extend(self._detect_and_download_files(soup, current_url))

            # Make the next move
            for link in soup.find_all('a', href=True):
                nei_url = urljoin(current_url, link['href'])
                # check if a valid url
                if not self._is_valid_url(nei_url):
                    continue
                # check if already visited
                if nei_url in visited:
                    continue
                queue.append(nei_url)
                visited.add(nei_url)
       
        # Update the scraped URLs file before returning results
        self._update_scraped_urls_file()
       
        return documents, newly_downloaded_files
                    

    def _langchain_load_url(self, url):
        """
        Use Langchain to load the content of a web page from a given URL.
        
        :param url: URL of the web page to load
        :return: List[Document] or None if the URL has already been scraped
        """
        if url in self.scraped_urls:
            print(f"URL already scraped: {url}")
            return None
        
        # Load the content from the URL
        loader = WebBaseLoader(url)
        doc = loader.load()
        
        # Add the URL to the set of scraped URLs
        self.scraped_urls.add(url)
        
        return doc
    

    def _load_scraped_urls(self):
        """
        Load previously scraped URLs from the text file into a set.
        If the file does not exist, create it.
        """
        scraped_urls = set()
        
        # Ensure the directory for the file exists
        file_dir = os.path.dirname(self.scraped_urls_file)
        if not os.path.exists(file_dir):
            os.makedirs(file_dir)

        # Create the file if it doesn't exist
        if not os.path.exists(self.scraped_urls_file):
            with open(self.scraped_urls_file, 'w') as f:
                pass  # Just create the file, no need to write anything yet

        # Load the URLs from the file
        if os.path.exists(self.scraped_urls_file):
            with open(self.scraped_urls_file, 'r') as f:
                for line in f:
                    scraped_urls.add(line.strip())

        return scraped_urls

    def _update_scraped_urls_file(self):
        """
        Update the scraped URLs text file with the latest set of scraped URLs.
        """
        with open(self.scraped_urls_file, 'w') as f:
            for url in self.scraped_urls:
                f.write(f"{url}\n")

    def _load_existing_files(self):
        existing_files = set()
        for root, _, files in os.walk(self.dir):
            for file in files:
                existing_files.add(os.path.join(root, file))
        return existing_files
    
    def _download_file(self, file_url):
        """
        Private method to download a file from a given URL. To be called by _detect_and_download_files().
        Currently supports [.pdf, .xlsx, .xls] file types.
        
        :param file_url: URL of the file to download
        :return: <str> Path to the downloaded file
        """
        local_filename = os.path.join(self.dir, os.path.basename(file_url))

        if local_filename in self.downloaded_files:
            print(f"File already downloaded: {local_filename}")
            return None
        
        # Perform the request and handle errors
        try:
            with requests.get(file_url, stream=True) as r:
                r.raise_for_status()  # Raise an error for bad status codes
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                    print(f"Downloaded: {local_filename}")
            self.downloaded_files.add(local_filename)
        except requests.exceptions.HTTPError as e:
            print(f"Failed to download {file_url}: {e}")
            return None  # Return None or handle the error as needed
        
        return local_filename
    
    def _detect_and_download_files(self, soup, base_url):
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

    def _is_valid_url(self, url):
        """
        Validate the URL to ensure it has both a scheme and network location.
        """
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme)
    
    
