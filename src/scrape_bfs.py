import requests
from bs4 import BeautifulSoup
from collections import deque
from urllib.parse import urljoin, urlparse

def is_valid_url(url):
    # Check if the URL is valid
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

def bfs_scrape(start_url, max_pages=50):
    visited = set()
    queue = deque([start_url])
    visited.add(start_url)

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        print(f"Scraping: {url}")

        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            print(f"Failed to scrape {url}: {e}")
            continue

        # Process the content (you can customize this)
        process_content(url, soup)

        # Find and enqueue all links on the page
        for a_tag in soup.find_all("a", href=True):
            next_url = a_tag['href']
            next_url = urljoin(url, next_url)  # Resolve relative URLs
            if is_valid_url(next_url) and next_url not in visited:
                queue.append(next_url)
                visited.add(next_url)

    print("Scraping completed.")

def process_content(url, soup):
    # Placeholder function to process the page content
    # You can extract specific data or save the content as needed
    print(f"Processing content from {url}")
    # Example: Save the title of the page
    title = soup.title.string if soup.title else 'No Title'
    print(f"Title: {title}")

if __name__ == "__main__":
    start_url = "https://example.com"  # Replace with the starting URL
    bfs_scrape(start_url)