import os
import json
import uuid
import shutil
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
# Import interview components
from interview import create_interview_graph, InterviewState
from resume import load_and_split_documents, get_role_from_resume
from langchain_core.messages import HumanMessage

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(title="Interview Agent API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory if it doesn't exist
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

# Store active interview sessions
active_sessions = {}

# Pydantic models
class InterviewSession(BaseModel):
    session_id: str
    resume_path: str
    current_question: str = ""
    scorecard: List[Dict[str, Any]] = []
    role: str = ""
    status: str = "initialized"  # initialized, in_progress, completed

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

class QuestionResponse(BaseModel):
    question: str
    evaluation: Optional[Dict[str, Any]] = None

@app.post("/upload-resume/", response_model=InterviewSession)
async def upload_resume(file: UploadFile = File(...)):
    """Upload a resume PDF to start an interview session"""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    # Generate unique session ID and save file
    session_id = str(uuid.uuid4())
    resume_path = UPLOADS_DIR / f"{session_id}_{file.filename}"
    
    with open(resume_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create new session
    session = InterviewSession(
        session_id=session_id,
        resume_path=str(resume_path),
        status="initialized"
    )
    
    # Extract role from resume
    try:
        docs = load_and_split_documents(str(resume_path))
        role = get_role_from_resume(docs)
        session.role = role
    except Exception as e:
        print(f"Error extracting role: {str(e)}")
        session.role = "Professional"
    
    active_sessions[session_id] = session
    return session

@app.get("/start-interview/{session_id}", response_model=QuestionResponse)
async def start_interview(session_id: str):
    """Start the interview and get the first question"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    # Initialize interview graph
    config = {"configurable": {"thread_id": session_id}}
    
    graph = create_interview_graph()
    
    # Initialize state
    state: InterviewState = {
        "messages": [
            HumanMessage(content="Start the technical interview")
        ],
        "scorecard": [],
        "current_question": "",
        "resume_path": session.resume_path
    }
    
    # Get first question
    first_question = ""
    for event in graph.stream(state, config, stream_mode="values"):
        if "messages" in event:
            for msg in event["messages"]:
                content = msg.content if hasattr(msg, 'content') else str(msg)
                if "?" in content:
                    first_question = content
                    break
            if first_question:
                break
    
    # Update session
    session.current_question = first_question
    session.status = "in_progress"
    active_sessions[session_id] = session
    
    return QuestionResponse(question=first_question)

@app.post("/submit-answer/", response_model=QuestionResponse)
async def submit_answer(answer_request: AnswerRequest):
    """Submit an answer and get the next question or evaluation"""
    session_id = answer_request.session_id
    user_answer = answer_request.answer
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    # Process through LangGraph
    config = {"configurable": {"thread_id": session_id}}
    
    graph = create_interview_graph()
    
    # Update state with user response
    state = {
        "messages": [HumanMessage(content=user_answer)],
        "scorecard": session.scorecard,
        "current_question": session.current_question,
        "resume_path": session.resume_path
    }
    
    # Process through LangGraph
    full_response = ""
    evaluation = None
    next_question = ""
    
    for event in graph.stream(state, config, stream_mode="values"):
        if "messages" in event:
            for msg in event["messages"]:
                content = msg.content if hasattr(msg, 'content') else str(msg)
                full_response += content + "\n"
                
                # Detect new questions
                if "?" in content and len(content.split()) > 5:
                    next_question = content
                
                # Try to parse evaluation
                try:
                    # Extract JSON if embedded in text
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match and "SCORE" in json_match.group():
                        json_data = json.loads(json_match.group())
                        evaluation = {
                            "question": json_data.get("question", session.current_question),
                            "human_answer": user_answer,
                            "llm_actual_answer": json_data.get("ACTUAL_ANSWER", ""),
                            "score": int(json_data["SCORE"]),
                            "reason": json_data.get("REASON", "")
                        }
                        session.scorecard.append(evaluation)
                except Exception as e:
                    print(f"Error parsing evaluation: {str(e)}")
    
    # Update session
    if next_question:
        session.current_question = next_question
    active_sessions[session_id] = session
    
    return QuestionResponse(
        question=next_question if next_question else full_response,
        evaluation=evaluation
    )

@app.get("/scorecard/{session_id}")
async def get_scorecard(session_id: str):
    """Get the current scorecard for a session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    # Calculate overall score
    total_score = sum(item["score"] for item in session.scorecard)
    avg_score = total_score / len(session.scorecard) if session.scorecard else 0
    
    return {
        "session_id": session_id,
        "role": session.role,
        "evaluations": session.scorecard,
        "overall_score": round(avg_score, 1),
        "total_questions": len(session.scorecard)
    }

@app.post("/end-interview/{session_id}")
async def end_interview(session_id: str):
    """End the interview session and finalize the scorecard"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    session.status = "completed"
    
    # Save results to file (optional)
    results_path = Path(f"results_{session_id}.json")
    with open(results_path, "w") as f:
        json.dump(session.scorecard, f, indent=2)
    
    return {"message": "Interview completed", "session_id": session_id}

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its associated files"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    # Delete resume file
    resume_path = Path(session.resume_path)
    if resume_path.exists():
        resume_path.unlink()
    
    # Delete results file if exists
    results_path = Path(f"results_{session_id}.json")
    if results_path.exists():
        results_path.unlink()
    
    # Remove session
    del active_sessions[session_id]
    
    return {"message": "Session deleted"}

# WebSocket for real-time interview
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_message(self, session_id: str, message: str):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    
    try:
        if session_id not in active_sessions:
            await websocket.send_json({"error": "Session not found"})
            await websocket.close()
            return
        
        session = active_sessions[session_id]
        
        # Send initial question if session is just starting
        if session.status == "initialized":
            response = await start_interview(session_id)
            await websocket.send_json({"type": "question", "content": response.question})
        
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)
            
            if data_json.get("type") == "answer":
                answer_request = AnswerRequest(
                    session_id=session_id,
                    answer=data_json.get("content", "")
                )
                
                response = await submit_answer(answer_request)
                
                # Send evaluation if available
                if response.evaluation:
                    await websocket.send_json({
                        "type": "evaluation",
                        "content": response.evaluation
                    })
                
                # Send next question
                await websocket.send_json({
                    "type": "question",
                    "content": response.question
                })
            
            elif data_json.get("type") == "end":
                await end_interview(session_id)
                await websocket.send_json({"type": "end", "content": "Interview completed"})
                break
    
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        manager.disconnect(session_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)