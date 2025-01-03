import datetime
import logging
import json
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse, StreamingResponse
from modules import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]

app = FastAPI()

origins = [
    "http://localhost:8000",
    "https://chat.alexbasile.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
    max_age=86400
)

PROJECT_ROOT = Path(__file__).parent.parent

@app.get("/")
async def read_root():
    return FileResponse(str(PROJECT_ROOT / "frontend" / "index.html"))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.get("/{filename}")
async def serve_frontend_files(filename: str):
    if filename in ["apple-touch-icon.png", "apple-touch-icon-precomposed.png"]:
        return Response(status_code=404)
    
    cache_headers = {
        "Cache-Control": f"no-cache, {'must-revalidate' if filename == 'favicon.ico' else 'no-store, must-revalidate'}",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    
    return FileResponse(
        str(PROJECT_ROOT / "frontend" / filename),
        headers=cache_headers
    )

@app.get("/api/resume")
async def send_resume():
    return Response(
        content=pull_resume(),
        media_type="text/plain",
        headers={
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

@app.get("/api/github")
def pull_github_digest():
    return Response(
        content=pull_github(),
        media_type="text/plain",
        headers={
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

@app.get("/api/linkedin")
def get_linkedin_digest():
    return Response(
        content=pull_linkedin(),
        media_type="text/plain",
        headers={
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

@app.get("/api/prompt_config")
async def prompt_config_route():
    return Response(
        content=json.dumps(get_prompt_config()),
        media_type="application/json"
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
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["*.pyc", "*.log"],
        reload_includes=["*.py", "*.html", "*.css", "*.js", "*.ico"],
    )