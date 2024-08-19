from langchain.document_loaders import WebBaseLoader

class WebScraper:
    def __init__(self, url):
        self.url = url
    
    def scrape(self):
        """
        Scrape the content from the given URL.
        
        :return: List of documents loaded from the URL
        """
        loader = WebBaseLoader(self.url)
        doc = loader.load()
        return doc