from langgraph.graph import StateGraph, END
from typing import Dict, Any, List
import re
import json
from dateutil import parser
from datetime import datetime, timedelta, timezone
from backend.calendar_utils import authenticate_google_calendar, check_availability, book_event, suggest_free_slots
import os
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

# Define the state structure (the agent's notepad)
def initial_state(user_message: str) -> Dict[str, Any]:
    return {
        "user_message": user_message,  # What the user just said
        "intent": None,                # What does the user want? (book, check, etc.)
        "date": None,                  # Date for the meeting
        "start_time": None,            # Start time
        "end_time": None,              # End time
        "availability": None,          # Is the slot free?
        "booking_confirmed": False,    # Did we book it?
        "response": "",               # What the agent will say back
        "suggestions": [],            # Alternative time suggestions
        "calendar_id": "aryanrai97861@gmail.com",  # Default calendar
        "summary": "Meeting",         # Default meeting title
        "description": None,          # Meeting description
        "attendees": None,           # Meeting attendees
        "needs_more_info": False,    # Flag to indicate if more info is needed
        "history": [
            {"role": "user", "content": user_message}
        ],
    }

def clean_gemini_response(response_text: str) -> str:
    """Clean Gemini response by removing markdown code blocks and extra whitespace."""
    # Remove markdown code blocks
    cleaned = re.sub(r'```json\s*', '', response_text)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    # Remove extra whitespace
    cleaned = cleaned.strip()
    return cleaned

# Improved Gemini integration with better error handling
def gemini_extract_intent_and_slots(message, prev_date=None, prev_time=None):
    """Call Google Gemini to extract intent, date, and time from the message."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable not set.")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Get current date for relative date parsing
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
You are a helpful assistant for booking calendar appointments. Extract the following from the user's message:
- intent: Must be one of: "book", "check", "cancel", "unknown"
- date: in YYYY-MM-DD format (today is {current_date})
- time: in HH:MM 24-hour format
- summary: brief meeting title if mentioned

Handle relative dates like "tomorrow", "next Friday", "today".
Handle time formats like "2pm", "14:00", "2:30 PM".

Examples:
User message: 'Book a meeting for tomorrow at 2pm'
Response: {{"intent": "book", "date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "time": "14:00", "summary": "Meeting"}}

User message: 'Do I have any free time this Friday?'
Response: {{"intent": "check", "date": "2024-06-28", "time": null, "summary": null}}

User message: 'Schedule dentist appointment next Monday 10:30 AM'
Response: {{"intent": "book", "date": "2024-07-01", "time": "10:30", "summary": "Dentist appointment"}}

User message: '{message}'
Previous date: {prev_date}
Previous time: {prev_time}

Respond with ONLY valid JSON in this exact format:
{{"intent": "...", "date": "...", "time": "...", "summary": "..."}}
"""
    
    try:
        response = model.generate_content(prompt)
        print(f"[Gemini raw response] {response.text}")
        
        # Clean the response
        cleaned_response = clean_gemini_response(response.text)
        print(f"[Gemini cleaned response] {cleaned_response}")
        
        # Parse JSON
        result = json.loads(cleaned_response)
        
        # Validate the result structure
        if "intent" not in result:
            result["intent"] = "unknown"
        if result["intent"] not in ["book", "check", "cancel", "unknown"]:
            result["intent"] = "unknown"
            
        return result
        
    except json.JSONDecodeError as e:
        print(f"[JSON Parse Error] {e}")
        print(f"[Raw response] {response.text}")
        # Fallback: try regex extraction
        return fallback_extraction(message)
    except Exception as e:
        print(f"[Gemini API Error] {e}")
        return {"intent": "unknown", "date": None, "time": None, "summary": None}

def fallback_extraction(message):
    """Fallback extraction using regex patterns."""
    result = {"intent": "unknown", "date": None, "time": None, "summary": None}
    
    # Extract intent
    message_lower = message.lower()
    if any(word in message_lower for word in ["book", "schedule", "reserve", "set up", "arrange"]):
        result["intent"] = "book"
    elif any(word in message_lower for word in ["free", "available", "busy", "slots", "check"]):
        result["intent"] = "check"
    elif any(word in message_lower for word in ["cancel", "delete", "remove"]):
        result["intent"] = "cancel"
    
    # Extract time using regex
    time_patterns = [
        r'\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?\b',
        r'\b(\d{1,2})\s*(am|pm|AM|PM)\b',
        r'\b(\d{1,2}):(\d{2})\b'
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, message)
        if match:
            if len(match.groups()) >= 3 and match.group(3):  # Has AM/PM
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0
                ampm = match.group(3).upper()
                if ampm == 'PM' and hour != 12:
                    hour += 12
                elif ampm == 'AM' and hour == 12:
                    hour = 0
            else:
                hour = int(match.group(1))
                minute = int(match.group(2)) if len(match.groups()) > 1 and match.group(2) else 0
            
            result["time"] = f"{hour:02d}:{minute:02d}"
            break
    
    # Extract relative dates
    today = datetime.now()
    if "tomorrow" in message_lower:
        result["date"] = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "today" in message_lower:
        result["date"] = today.strftime("%Y-%m-%d")
    
    return result

def gemini_conversational_reply(conversation_history: List[Dict[str, str]]):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    # Format the conversation history for the prompt
    history_str = ""
    for msg in conversation_history:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"
    prompt = f"""
You are a friendly calendar assistant. Here is the conversation so far:
{history_str}

Based on the conversation, reply naturally. If you need more info, ask for it. If you can book, confirm with the user. If the user is making small talk, respond appropriately.

Also, if you detect a booking intent, extract: date (YYYY-MM-DD), time (HH:MM 24-hour), summary (meeting title).

Respond in JSON:
{{
  "reply": "...",
  "intent": "...",
  "date": "...",
  "time": "...",
  "summary": "..."
}}
"""
    response = model.generate_content(prompt)
    # Clean markdown if present
    cleaned = re.sub(r'```json\s*', '', response.text)
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()
    result = json.loads(cleaned)
    return result

def conversational_node(state: Dict[str, Any]) -> Dict[str, Any]:
    history = state.get("history", [])
    gemini_result = gemini_conversational_reply(history)
    print(f"[Gemini conversational result] {gemini_result}")
    state["response"] = gemini_result.get("reply", "Sorry, I didn't understand that.")
    state["intent"] = gemini_result.get("intent", "unknown")
    if gemini_result.get("date"):
        state["date"] = gemini_result["date"]
    if gemini_result.get("time"):
        state["start_time"] = gemini_result["time"]
    if gemini_result.get("summary"):
        state["summary"] = gemini_result["summary"]
    if gemini_result.get("email"):
        state["attendees"] = [gemini_result["email"]]
    state.setdefault("history", []).append({"role": "assistant", "content": state["response"]})
    # NEW: Handle 'show my meetings/appointments' intent
    if state["intent"] in ["show_meetings", "show_appointments", "list_meetings", "list_appointments"]:
        service = authenticate_google_calendar()
        from backend.calendar_utils import list_upcoming_events
        events = list_upcoming_events(service, state["calendar_id"], max_results=5)
        if not events:
            state["response"] = "You have no upcoming meetings or appointments."
        else:
            event_lines = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                summary = event.get('summary', '(No Title)')
                link = event.get('htmlLink', '')
                event_lines.append(f"- {summary} at {start} [link]({link})")
            state["response"] = "Here are your next meetings:\n" + "\n".join(event_lines)
        state["needs_more_info"] = False
        return state
    if state["intent"] == "book":
        if not state.get("date"):
            state["needs_more_info"] = True
        elif not state.get("start_time"):
            state["needs_more_info"] = True
        elif not state.get("attendees"):
            state["response"] = "What is your email address so I can send you the invite?"
            state["needs_more_info"] = True
        else:
            state["needs_more_info"] = False
    elif state["intent"] == "check":
        if not state.get("date"):
            state["needs_more_info"] = True
        else:
            state["needs_more_info"] = False
    else:
        state["needs_more_info"] = True
    return state

# Node 2: Check availability
def check_availability_node(state: Dict[str, Any]) -> Dict[str, Any]:
    if state.get("needs_more_info"):
        return state
    if state["intent"] == "check":
        if not state.get("date"):
            state["response"] = "Missing date for availability check."
            return state
        date_str = state["date"]
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            start_of_day = date_obj.replace(hour=9, minute=0)
        except Exception as e:
            state["response"] = f"Could not parse date: {e}"
            return state
        service = authenticate_google_calendar()
        suggestions = suggest_free_slots(service, state["calendar_id"], start_of_day, slot_duration_minutes=60)
        if suggestions:
            suggestion_str = ", ".join([s.strftime("%H:%M") for s in suggestions])
            state["response"] = f"Available slots on {date_str}: {suggestion_str}"
        else:
            state["response"] = f"No free slots found on {date_str}."
        return state
    if not state.get("date") or not state.get("start_time"):
        state["response"] = "Missing date or time for availability check."
        return state
    date_str = state["date"]
    time_str = state["start_time"]
    try:
        start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        start_dt = start_dt.replace(tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(hours=1)
        state["end_time"] = end_dt.strftime("%H:%M")
    except Exception as e:
        state["response"] = f"Could not parse date/time: {e}"
        return state
    try:
        service = authenticate_google_calendar()
        is_free = check_availability(service, state["calendar_id"], start_dt, end_dt)
        state["availability"] = is_free
        if is_free:
            state["response"] = f"Great! The slot on {date_str} at {time_str} is available. Shall I book it for you?"
        else:
            # Always suggest alternative slots if not free
            suggestions = suggest_free_slots(service, state["calendar_id"], start_dt, slot_duration_minutes=60)
            if suggestions:
                suggestion_str = ", ".join([s.strftime("%H:%M") for s in suggestions[:3]])
                state["response"] = f"Sorry, {time_str} on {date_str} is not available. How about: {suggestion_str}?"
                state["suggestions"] = [s.strftime("%H:%M") for s in suggestions]
            else:
                state["response"] = f"Sorry, {time_str} on {date_str} is not available, and no other slots are free that day."
                state["suggestions"] = []
    except Exception as e:
        state["response"] = f"Error checking availability: {e}"
    return state

# Node 3: Booking
def booking_node(state: Dict[str, Any]) -> Dict[str, Any]:
    if not state.get("availability"):
        state["response"] = "Cannot book: slot is not available or not checked yet."
        return state
    if not all([state.get("date"), state.get("start_time")]):
        state["response"] = "Cannot book: missing date or time information."
        return state
    date_str = state["date"]
    time_str = state["start_time"]
    try:
        start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        start_dt = start_dt.replace(tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(hours=1)
    except Exception as e:
        state["response"] = f"Could not parse date/time for booking: {e}"
        return state
    try:
        service = authenticate_google_calendar()
        attendees = state.get("attendees")
        event = book_event(
            service, 
            state["calendar_id"], 
            start_dt, 
            end_dt, 
            state.get("summary", "Meeting"),
            state.get("description"),
            attendees
        )
        state["booking_confirmed"] = True
        # Always provide the event link after booking
        event_link = event.get('htmlLink', 'N/A')
        state["response"] = f"Perfect! Your '{state.get('summary', 'Meeting')}' is booked for {date_str} at {time_str}. Event link: {event_link}"
    except Exception as e:
        state["response"] = f"Booking failed: {e}"
    return state

# Build the agent graph with proper routing
def build_agent_graph():
    graph = StateGraph(dict)
    
    # Add nodes
    graph.add_node("conversational", conversational_node)
    graph.add_node("check_availability", check_availability_node)
    graph.add_node("booking", booking_node)
    
    # Set entry point
    graph.set_entry_point("conversational")
    
    # Add conditional edges
    graph.add_conditional_edges(
        "conversational",
        lambda state: "check_availability" if state["intent"] in ["book", "check"] and not state.get("needs_more_info") else END,
        {"check_availability": "check_availability", END: END}
    )
    
    graph.add_conditional_edges(
        "check_availability",
        lambda state: "booking" if state.get("availability") and state["intent"] == "book" else END,
        {"booking": "booking", END: END}
    )
    
    graph.add_edge("booking", END)
    
    return graph.compile()

# Main execution function
def run_agent(user_message: str, state: Dict[str, Any] = None):
    """Run the agent with a user message."""
    if state is None:
        state = initial_state(user_message)
    else:
        state["user_message"] = user_message
        state.setdefault("history", []).append({"role": "user", "content": user_message})
        state["needs_more_info"] = False  # Reset flag for new message
    
    agent = build_agent_graph()
    
    try:
        result = agent.invoke(state)
        return result
    except Exception as e:
        print(f"Agent execution error: {e}")
        return {**state, "response": f"Sorry, I encountered an error: {e}"}

if __name__ == "__main__":
    print("Calendar Booking Agent - Type 'quit' to exit")
    state = None
    
    while True:
        user_message = input("\nYou: ")
        if user_message.lower() in ['quit', 'exit', 'bye']:
            print("Goodbye!")
            break
            
        result = run_agent(user_message, state)
        print(f"Agent: {result['response']}")
        
        # Maintain state for context
        state = result