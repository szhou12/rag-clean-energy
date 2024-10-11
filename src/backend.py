import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, Form
from fastapi import __version__ as fastapi_version
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rag import RAGAgent

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize RAGAgent
MYSQL_CONFIG = {
    'user': 'root',
    'host': 'localhost',
    'port': 3306,
    'password': os.getenv('MYSQL_PASSWORD'),
    'db_name': 'rmi_test'
}

agent = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Event: Initialize RAGAgent and other resources
    print("Starting up FastAPI with resources...")
    rag_agent = RAGAgent(mysql_config=MYSQL_CONFIG, vector_db="db_chroma")
    agent['rag_agent'] = rag_agent

    # Yield control to allow the application to run
    yield

    # Shutdown Event: Cleanup resources after shutdown
    print("Shutting down FastAPI and cleaning up resources...")
    agent['rag_agent'].close()
    agent.clear() # clear the agent dictionary



# create a FastAPI application instance, name it 'app'
app = FastAPI(lifespan=lifespan)

# Define Pydantic models for request (input) and response (output)
class ChatInput(BaseModel):
    user_query: str
    chat_history: list

# API endpoint to handle chat inputs
@app.post("/chat")
async def handle_chat(input: ChatInput):
    try:
        ai_response = agent['rag_agent'].handle_query(input.user_query, input.chat_history)
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
        agent['rag_agent'].process_file(file_path, language)
        return {"status": "File processed successfully", "file_path": file_path}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# API endpoint to scrape URLs
@app.post("/scrape-url/")
async def scrape_url(url: str, max_pages: int = 1, autodownload: bool = False, language: str = "en"):
    try:
        num_docs, num_downloaded_files = agent['rag_agent'].process_url(url, max_pages=max_pages, autodownload=autodownload, language=language)

        return {
            "status": "Scraping completed!", 
            "num_docs": num_docs, 
            "num_downloaded_files": num_downloaded_files, 
            "scraped_urls": list(agent['rag_agent'].scraper.scraped_urls)
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Testing API endpoint
@app.get("/server-status")
async def server_status():
    response = {
        "server_status": "Server is running!",
        "fastapi_version": fastapi_version,
        "python_verion": sys.version_info,
    }
    return response