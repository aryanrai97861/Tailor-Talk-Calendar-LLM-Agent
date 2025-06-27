import streamlit as st
import requests

st.title("Tailor Talk: Calendar Booking Assistant")

# Store chat history and slots in session state
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "date" not in st.session_state:
    st.session_state["date"] = None
if "start_time" not in st.session_state:
    st.session_state["start_time"] = None

# Chat input
user_input = st.chat_input("Type your message...")

# Display chat history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# On user input
if user_input:
    # Add user message to history
    st.session_state["messages"].append({"role": "user", "content": user_input})
    # Send to FastAPI backend with slot state
    try:
        payload = {
            "message": user_input,
            "date": st.session_state["date"],
            "start_time": st.session_state["start_time"]
        }
        response = requests.post(
        "https://tailor-talk-calendar-llm-agent-2.onrender.com/chat",
        json=payload,
        timeout=10
        )
        data = response.json()
        agent_reply = data.get("response", "(No response)")
        # Update slots if returned by backend
        if "date" in data:
            st.session_state["date"] = data["date"]
        if "start_time" in data:
            st.session_state["start_time"] = data["start_time"]
    except Exception as e:
        agent_reply = f"Error: {e}"
    # Add agent response to history
    st.session_state["messages"].append({"role": "assistant", "content": agent_reply})
    st.rerun() 