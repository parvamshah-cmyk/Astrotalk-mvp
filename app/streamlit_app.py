"""
AstroTalk AI Astrologer — Chat Interface

Run with:
    streamlit run app/streamlit_app.py
"""

import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from app.letta_client_helper import (
    get_client,
    get_or_create_agent,
    send_message,
    extract_assistant_text,
    get_conversation_history,
)

# --- Page Config ---
st.set_page_config(
    page_title="AstroTalk AI Astrologer",
    page_icon="\u2728",
    layout="centered",
)

st.title("AstroTalk AI Astrologer")
st.caption("Your personal AI-powered astrological consultant")

# --- Session State ---
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "agent_id" not in st.session_state:
    st.session_state.agent_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "initialized" not in st.session_state:
    st.session_state.initialized = False

# --- Sidebar: Login ---
with st.sidebar:
    st.header("User Login")

    login_mode = st.radio(
        "Are you a new or returning user?",
        ["New User", "Returning User"],
    )

    if login_mode == "Returning User":
        user_id_input = st.text_input(
            "Enter your User ID",
            placeholder="e.g. a1b2c3d4-e5f6-...",
        )
        if st.button("Connect", key="connect_returning"):
            if user_id_input.strip():
                st.session_state.user_id = user_id_input.strip()
                st.session_state.agent_id = None
                st.session_state.messages = []
                st.session_state.initialized = False
                st.rerun()
            else:
                st.error("Please enter a valid User ID.")
    else:
        st.info(
            "Click 'Start New Session' to begin. "
            "The astrologer will ask for your birth details."
        )
        if st.button("Start New Session", key="connect_new"):
            new_id = str(uuid.uuid4())
            st.session_state.user_id = new_id
            st.session_state.agent_id = None
            st.session_state.messages = []
            st.session_state.initialized = False
            st.rerun()

    # Show session info
    if st.session_state.user_id:
        st.divider()
        st.success(f"User ID:")
        st.code(st.session_state.user_id, language=None)
        st.caption("Save this ID to return to your session later.")

        if st.button("Logout"):
            st.session_state.user_id = None
            st.session_state.agent_id = None
            st.session_state.messages = []
            st.session_state.initialized = False
            st.rerun()

# --- Main Chat Area ---
if not st.session_state.user_id:
    st.info("Please log in or start a new session from the sidebar.")
    st.stop()

# --- Initialize Letta Client and Agent ---
try:
    client = get_client()
except Exception as e:
    st.error(f"Cannot connect to Letta server: {e}")
    st.info("Make sure the Letta server is running: docker compose up -d")
    st.stop()

if st.session_state.agent_id is None:
    with st.spinner("Setting up your astrologer..."):
        try:
            agent_id = get_or_create_agent(client, st.session_state.user_id)
            st.session_state.agent_id = agent_id
        except Exception as e:
            st.error(f"Error setting up agent: {e}")
            st.stop()

# --- Load History or Send Initial Message ---
if not st.session_state.initialized:
    with st.spinner("Loading your session..."):
        # Check for existing conversation history
        history = get_conversation_history(client, st.session_state.agent_id)

        if history:
            # Returning user with existing conversation
            st.session_state.messages = history
        else:
            # First time — send initial handshake message
            initial_msg = (
                f"Hello! My user ID is {st.session_state.user_id}. "
                "Please check if you have my birth details on file."
            )
            try:
                response_msgs = send_message(
                    client, st.session_state.agent_id, initial_msg
                )
                assistant_text = extract_assistant_text(response_msgs)

                st.session_state.messages.append(
                    {"role": "user", "content": initial_msg}
                )
                if assistant_text:
                    st.session_state.messages.append(
                        {"role": "assistant", "content": assistant_text}
                    )
            except Exception as e:
                st.error(f"Error during initialization: {e}")

        st.session_state.initialized = True
        st.rerun()

# --- Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Chat Input ---
if prompt := st.chat_input("Ask the astrologer..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent response
    with st.chat_message("assistant"):
        with st.spinner("Consulting the stars..."):
            try:
                response_msgs = send_message(
                    client, st.session_state.agent_id, prompt
                )
                assistant_text = extract_assistant_text(response_msgs)

                if assistant_text:
                    st.markdown(assistant_text)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": assistant_text}
                    )
                else:
                    fallback = "I'm processing your request. Please give me a moment and try again."
                    st.markdown(fallback)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": fallback}
                    )
            except Exception as e:
                error_msg = f"I encountered an error: {str(e)}"
                st.markdown(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
