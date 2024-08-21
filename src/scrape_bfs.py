import streamlit as st
from rag.scrapers.web_scraper import WebScraper

# Set up the Streamlit app
st.title("Web Scraper Interface")

# Input fields for user parameters
url = st.text_input("Enter the URL to start scraping from:")
max_pages = st.number_input("Maximum number of pages to scrape:", min_value=1, value=1)
autodownload = st.checkbox("Enable autodownload of attached files", value=False)

# Initialize WebScraper
scraper = WebScraper()

# Button to start scraping
if st.button("Start Scraping"):
    if url:
        with st.spinner("Scraping..."):
            try:
                # Call the scrape method
                documents, downloaded_files = scraper.scrape(url, max_pages=max_pages, autodownload=autodownload)
                
                # Display results
                st.success(f"Scraping completed! {len(documents)} pages scraped.")
                
                if autodownload:
                    st.write(f"Files downloaded: {len(downloaded_files)}")
                    for file in downloaded_files:
                        st.write(file)
                        
                st.write("scraped URL:")
                for url in scraper.scraped_urls:
                    st.write(url)
                # Optionally, display document contents (this could be a lot of text!)
                st.write("Sample of scraped content:")
                for i, doc in enumerate(documents[:3]):  # Displaying the first 3 documents
                    st.write(f"Document {i+1}:")
                    st.write(doc)

                
            except Exception as e:
                st.error(f"An error occurred: {e}")
    else:
        st.warning("Please enter a valid URL.")