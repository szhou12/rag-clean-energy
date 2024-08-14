import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import streamlit as st

def scrape_and_download(url, download_folder='downloads'):
    download_dir = os.path.join(os.path.dirname(__file__), '..', download_folder)
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    file_extensions = ['.pdf', '.zip', '.docx', '.xlsx', '.jpg', '.png']
    links = soup.find_all('a', href=True)

    downloaded_files = []
    for link in links:
        href = link['href']
        if any(href.endswith(ext) for ext in file_extensions):
            file_url = urljoin(url, href)
            file_name = download_file(file_url, download_dir)
            downloaded_files.append(file_name)

    return downloaded_files

def download_file(file_url, download_dir):
    local_filename = os.path.join(download_dir, os.path.basename(file_url))
    with requests.get(file_url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

st.title('Web Scraper for Downloadable Files')
url = st.text_input('Enter URL to scrape', '')

if st.button('Scrape and Download'):
    if url:
        with st.spinner('Scraping and downloading...'):
            try:
                downloaded_files = scrape_and_download(url)
                if downloaded_files:
                    st.success(f'Downloaded {len(downloaded_files)} files:')
                    for file in downloaded_files:
                        st.write(file)
                else:
                    st.warning('No downloadable files found.')
            except Exception as e:
                st.error(f'An error occurred: {e}')
    else:
        st.warning('Please enter a URL.')