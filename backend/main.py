from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
from .agent import initial_state, run_agent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Calendar Booking Agent API", version="1.0.0")

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage (replace with proper session management in production)
sessions: Dict[str, Dict[str, Any]] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    calendar_id: Optional[str] = "aryanrai97861@gmail.com"
    
class ChatResponse(BaseModel):
    response: str
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    intent: Optional[str] = None
    availability: Optional[bool] = None
    booking_confirmed: Optional[bool] = None
    suggestions: Optional[list] = None
    session_id: str
    needs_more_info: Optional[bool] = None

class SessionRequest(BaseModel):
    session_id: str

class SessionResponse(BaseModel):
    session_id: str
    state: Dict[str, Any]

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "Calendar Booking Agent API is running"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Main chat endpoint for interacting with the calendar booking agent."""
    try:
        session_id = request.session_id
        user_message = request.message
        calendar_id = request.calendar_id
        
        logger.info(f"Processing message for session {session_id}: {user_message}")
        
        # Get or create session state
        if session_id in sessions:
            state = sessions[session_id].copy()
            logger.info(f"Continuing session {session_id} with existing state")
        else:
            state = initial_state(user_message)
            state["calendar_id"] = calendar_id
            logger.info(f"Created new session {session_id}")
        
        # Run the agent
        result = run_agent(user_message, state)
        
        # Update session
        sessions[session_id] = result
        
        logger.info(f"Agent response for session {session_id}: {result['response']}")
        
        # Return response
        return ChatResponse(
            response=result["response"],
            date=result.get("date"),
            start_time=result.get("start_time"),
            end_time=result.get("end_time"),
            intent=result.get("intent"),
            availability=result.get("availability"),
            booking_confirmed=result.get("booking_confirmed", False),
            suggestions=result.get("suggestions", []),
            session_id=session_id,
            needs_more_info=result.get("needs_more_info", False)
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/new-session")
async def create_new_session(calendar_id: str = "aryanrai97861@gmail.com"):
    """Create a new session for the agent."""
    import uuid
    session_id = str(uuid.uuid4())
    
    # Initialize empty state for new session
    state = {
        "user_message": "",
        "intent": None,
        "date": None,
        "start_time": None,
        "end_time": None,
        "availability": None,
        "booking_confirmed": False,
        "response": "Hello! I'm your calendar booking assistant. I can help you book meetings, check availability, or cancel appointments. What would you like to do?",
        "suggestions": [],
        "calendar_id": calendar_id,
        "summary": "Meeting",
        "description": None,
        "attendees": None,
        "needs_more_info": False,
    }
    
    sessions[session_id] = state
    logger.info(f"Created new session: {session_id}")
    
    return {"session_id": session_id, "message": state["response"]}

@app.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get the current state of a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        session_id=session_id,
        state=sessions[session_id]
    )

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del sessions[session_id]
    logger.info(f"Deleted session: {session_id}")
    return {"message": f"Session {session_id} deleted successfully"}

@app.get("/sessions")
async def list_sessions():
    """List all active sessions (for debugging)."""
    return {
        "active_sessions": len(sessions),
        "session_ids": list(sessions.keys())
    }

# Quick booking endpoint for direct API usage
@app.post("/quick-book")
async def quick_book(
    date: str,
    time: str,
    summary: str = "Meeting",
    description: Optional[str] = None,
    calendar_id: str = "aryanrai97861@gmail.com"
):
    """Quick booking endpoint for direct API calls."""
    try:
        # Create a temporary state for quick booking
        state = initial_state(f"Book {summary} on {date} at {time}")
        state.update({
            "calendar_id": calendar_id,
            "date": date,
            "start_time": time,
            "summary": summary,
            "description": description,
            "intent": "book"
        })
        
        # Run the agent
        result = run_agent("", state)
        
        if result.get("booking_confirmed"):
            return {
                "success": True,
                "message": result["response"],
                "event_details": {
                    "date": result["date"],
                    "start_time": result["start_time"],
                    "end_time": result["end_time"],
                    "summary": result["summary"]
                }
            }
        else:
            return {
                "success": False,
                "message": result["response"],
                "availability": result.get("availability"),
                "suggestions": result.get("suggestions", [])
            }
            
    except Exception as e:
        logger.error(f"Quick booking error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Booking failed: {str(e)}")

# Check availability endpoint
@app.post("/check-availability")
async def check_availability_endpoint(
    date: str,
    calendar_id: str = "aryanrai97861@gmail.com"
):
    """Check availability for a specific date."""
    try:
        # Create a temporary state for availability check
        state = initial_state(f"Check availability for {date}")
        state.update({
            "calendar_id": calendar_id,
            "date": date,
            "intent": "check"
        })
        
        # Run the agent
        result = run_agent("", state)
        
        return {
            "date": result["date"],
            "available_slots": result.get("suggestions", []),
            "message": result["response"]
        }
        
    except Exception as e:
        logger.error(f"Availability check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Availability check failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)