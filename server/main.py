import time
import logging
import datetime
import os
from pathlib import Path
from contextlib import asynccontextmanager

# Initialize timing
startup_time = time.time()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True
)
logger = logging.getLogger(__name__)

def log_time(message):
    logger.info(f"STARTUP TIMING - {message}: {time.time() - startup_time:.2f}s")

log_time("Starting imports")

from pydantic import BaseModel
log_time("Pydantic imported")

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse, StreamingResponse
log_time("FastAPI and dependencies imported")

from linkedin import pull_linkedin
from github import pull_github
from resume import pull_resume
from generator import generate_stream
log_time("Local modules imported")

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
log_time("Project root configured")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
log_time("Models defined")

@asynccontextmanager
async def lifespan(app: FastAPI):
    log_time("Starting application startup")
    yield
    log_time("Application shutdown")

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)
log_time("FastAPI app created")

# Mount static files using absolute path
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "client")), name="static")
log_time("Static files mounted")

# Configure CORS
origins = [
    os.getenv("ALLOWED_ORIGINS", "http://localhost:8000"),
    "https://2m3b4rdkqwbfy5xca6cjbbjey40ickzn.lambda-url.us-west-2.on.aws",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
    max_age=86400
)
log_time("CORS configured")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "fast-chat",
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.get("/")
async def read_root():
    return FileResponse(str(PROJECT_ROOT / "client" / "index.html"))

@app.get("/{filename}")
async def serve_client_files(filename: str):
    response = FileResponse(str(PROJECT_ROOT / "client" / filename))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/api/resume")
async def send_resume():
    resume = pull_resume()
    return Response(
        content=resume,
        media_type="text/plain",
        headers={
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

@app.get("/api/github")
def pull_github_digest():
    github = pull_github()
    return Response(
        content=github,
        media_type="text/plain",
        headers={
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

@app.get("/api/linkedin")
def get_linkedin_digest():
    linkedin = pull_linkedin()
    return Response(
        content=linkedin,
        media_type="text/plain",
        headers={
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

@app.post("/api/chat")
async def chat_completion(request: ChatRequest):
    try:
        messages = [msg.model_dump() for msg in request.messages]
        return StreamingResponse(
            generate_stream(messages),
            media_type="text/event-stream",
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': '*'
            }
        )
    except Exception as e:
        logger.error(f"Error in chat completion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    log_time("Starting uvicorn")
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["*.pyc", "*.log"],
        reload_includes=["*.py", "*.html", "*.css", "*.js"],
        log_level="info"
    )