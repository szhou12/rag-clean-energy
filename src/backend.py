from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rag import RAGAgent
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize RAGAgent
mysql_config = {
    'user': 'root',
    'host': 'localhost',
    'port': 3306,
    'password': os.getenv('MYSQL_PASSWORD'),
    'db_name': 'rmi_test'
}

rag_agent = RAGAgent(mysql_config=mysql_config, vector_db="db_chroma")

# create a FastAPI application instance, name it 'app'
app = FastAPI()

# Define Pydantic models for request (input) and response (output)
class ChatInput(BaseModel):
    user_query: str
    chat_history: list

# API endpoint to handle chat inputs
@app.post("/chat")
async def handle_chat(input: ChatInput):
    try:
        ai_response = rag_agent.handle_query(input.user_query, input.chat_history)
        return JSONResponse(content={"response": ai_response})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
# API endpoint to upload files
@app.post("/upload-file/")
async def upload_file(file: UploadFile, language: str = Form("en")):
    try:
        temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')
        file_path = os.path.join(temp_dir, file.filename)
        # save file to temp directory
        with open(file_path, "wb") as f:
            f.write(await file.read())
        rag_agent.process_file(file_path, language)
        return {"status": "File processed successfully", "file_path": file_path}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# API endpoint to scrape URLs
@app.post("/scrape-url/")
async def scrape_url(url: str, max_pages: int = 1, autodownload: bool = False, language: str = "en"):
    try:
        num_docs, num_downloaded_files = rag_agent.process_url(url, max_pages=max_pages, autodownload=autodownload, language=language)

        return {
            "status": "Scraping completed!", 
            "num_docs": num_docs, 
            "num_downloaded_files": num_downloaded_files, 
            "scraped_urls": list(rag_agent.scraper.scraped_urls)
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

