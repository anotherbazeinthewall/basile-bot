import datetime
from modules import *
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse, StreamingResponse

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
    response = FileResponse(str(PROJECT_ROOT / "frontend" / filename))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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
        reload_includes=["*.py", "*.html", "*.css", "*.js"],
    )