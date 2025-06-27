# Tailor Talk: Conversational Calendar Booking Agent

A conversational AI agent that helps users book appointments on Google Calendar through a natural, back-and-forth chat interface.

## Features
- Accepts user input in natural language
- Guides the conversation to book a slot, check availability, or list meetings
- Checks Google Calendar for availability and books confirmed time slots
- Suggests alternative time slots if a requested slot is busy
- Invites users as attendees so they receive calendar invites and can access event links
- Powered by FastAPI (backend), LangGraph (agent logic), Streamlit (frontend), and Google Gemini (LLM)

## Tech Stack
- **Backend:** Python, FastAPI
- **Agent Framework:** LangGraph
- **Frontend:** Streamlit
- **Calendar Integration:** Google Calendar API (service account)
- **LLM:** Google Gemini (via API)

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/tailor-talk.git
cd tailor-talk
```

### 2. Backend Setup
- Create a Python virtual environment and activate it:
  ```bash
  python -m venv .venv
  source .venv/bin/activate  # On Windows: .venv\Scripts\activate
  ```
- Install backend dependencies:
  ```bash
  pip install -r backend/requirements.txt
  ```
- Place your Google service account `credentials.json` in the `backend/` directory.
- Create a `.env` file in the project root with your Gemini API key:
  ```
  GOOGLE_API_KEY=your-gemini-api-key-here
  ```
- Share your Google Calendar with the service account email (found in `credentials.json`).
- Start the backend:
  ```bash
  uvicorn backend.main:app --reload
  ```

### 3. Frontend Setup
- Install frontend dependencies:
  ```bash
  pip install -r frontend/requirements.txt
  ```
- Start the Streamlit frontend:
  ```bash
  streamlit run frontend/app.py
  ```

### 4. Usage
- Open the Streamlit app in your browser.
- Chat with the agent to book, check, or list meetings.
- Provide your email when booking to receive a calendar invite and event link.

## Security Notes
- **Never commit your `.env` or `credentials.json` to GitHub!**
- This project is for demo/dev use. For production, use secure session storage and restrict CORS origins.

## Example Conversations
- "Book a meeting for tomorrow at 2pm."
- "Do you have any free time this Friday?"
- "Show my meetings."

## License
MIT 