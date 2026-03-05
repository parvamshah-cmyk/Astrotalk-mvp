"""
Letta client helper — manages agent lifecycle, messaging, and tool registration.
"""

import json
import sys
import os
from typing import Optional, Generator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from letta_client import Letta

from app.config import (
    LETTA_BASE_URL,
    LLM_MODEL,
    EMBEDDING_MODEL,
    SYSTEM_PROMPT_PATH,
)


def get_client() -> Letta:
    """Return a Letta client connected to the local server."""
    return Letta(base_url=LETTA_BASE_URL)


def ensure_letta_setup(client: Letta):
    """
    Ensure the Letta server has the Gemini provider and sandbox config.
    Idempotent — safe to call on every Streamlit startup.
    """
    import requests

    base = LETTA_BASE_URL.rstrip("/")

    # 1. Register Anthropic provider if not present
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            resp = requests.get(f"{base}/v1/providers/", timeout=10)
            providers = resp.json() if resp.ok else []
            has_anthropic = any(
                p.get("provider_type") == "anthropic" for p in providers
            )
            if not has_anthropic:
                requests.post(
                    f"{base}/v1/providers/",
                    json={
                        "provider_type": "anthropic",
                        "api_key": anthropic_key,
                        "name": "anthropic",
                    },
                    timeout=10,
                )
        except Exception:
            pass

    # 2. Ensure sandbox config has pymongo[srv]
    try:
        resp = requests.get(f"{base}/v1/sandbox-config/", timeout=10)
        configs = resp.json() if resp.ok else []
        has_pymongo = False
        for cfg in configs:
            reqs = cfg.get("config", {}).get("pip_requirements", [])
            for r in reqs:
                if "pymongo" in r.get("name", ""):
                    has_pymongo = True
                    break
        if not has_pymongo:
            requests.post(
                f"{base}/v1/sandbox-config/local",
                json={
                    "sandbox_dir": "/root/.letta/tool_execution_dir",
                    "use_venv": True,
                    "venv_name": "venv",
                    "pip_requirements": [{"name": "pymongo[srv]"}],
                },
                timeout=10,
            )
    except Exception:
        pass


def load_system_prompt() -> str:
    """Load the system prompt from file."""
    with open(SYSTEM_PROMPT_PATH, "r") as f:
        return f.read().strip()


def find_agent_for_user(client: Letta, user_id: str) -> Optional[str]:
    """
    Look up an existing Letta agent for this user.
    Agent naming convention: astrotalk-user-{user_id}
    Returns agent_id if found, None otherwise.
    """
    agent_name = f"astrotalk-user-{user_id}"
    try:
        results = client.agents.list(name=agent_name)
        agents = list(results)
        if agents:
            return agents[0].id
    except Exception:
        pass
    return None


def create_agent_for_user(client: Letta, user_id: str) -> str:
    """
    Create a new Letta agent for this user.
    Registers tools (idempotent) and configures memory blocks.
    Returns the new agent_id.
    """
    from tools.mongo_tools import fetch_user_birth_details, save_user_birth_details

    # Upsert tools (idempotent — creates or updates)
    fetch_tool = client.tools.upsert_from_function(
        func=fetch_user_birth_details,
        tags=["astrotalk", "mongodb"],
        pip_requirements=[{"name": "pymongo"}],
    )
    save_tool = client.tools.upsert_from_function(
        func=save_user_birth_details,
        tags=["astrotalk", "mongodb"],
        pip_requirements=[{"name": "pymongo"}],
    )

    system_prompt = load_system_prompt()
    agent_name = f"astrotalk-user-{user_id}"

    agent = client.agents.create(
        name=agent_name,
        description=f"AstroTalk astrologer for user {user_id}",
        model=LLM_MODEL,
        embedding=EMBEDDING_MODEL,
        system=system_prompt,
        memory_blocks=[
            {
                "label": "persona",
                "value": (
                    "I am an expert Vedic and Western astrologer from AstroTalk. "
                    "I provide insightful, compassionate, and personalized "
                    "astrological readings. I always check for existing birth "
                    "details before asking."
                ),
                "limit": 5000,
            },
            {
                "label": "human",
                "value": json.dumps(
                    {
                        "user_id": user_id,
                        "name": None,
                        "date_of_birth": None,
                        "time_of_birth": None,
                        "place_of_birth": None,
                        "birth_details_collected": False,
                    }
                ),
                "limit": 3000,
                "description": (
                    "Information about the current user. Contains user_id and "
                    "birth details. Update when details are fetched or collected."
                ),
            },
            {
                "label": "astro_context",
                "value": "No birth chart computed yet. Awaiting birth details.",
                "limit": 5000,
                "description": (
                    "Astrological context for the current user. Update with "
                    "chart data, planetary positions, and reading insights."
                ),
            },
        ],
        tool_ids=[fetch_tool.id, save_tool.id],
        include_base_tools=True,
        tags=["astrotalk", f"user:{user_id}"],
    )
    return agent.id


def get_or_create_agent(client: Letta, user_id: str) -> str:
    """Get existing agent for user or create a new one. Returns agent_id."""
    agent_id = find_agent_for_user(client, user_id)
    if agent_id:
        return agent_id
    return create_agent_for_user(client, user_id)


def send_message(client: Letta, agent_id: str, user_message: str) -> list:
    """
    Send a message to the agent and return the response messages.
    """
    response = client.agents.messages.create(
        agent_id=agent_id,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.messages


def extract_assistant_text(messages: list) -> str:
    """Extract assistant message text from a list of Letta response messages."""
    parts = []
    for msg in messages:
        if hasattr(msg, "message_type") and msg.message_type == "assistant_message":
            content = getattr(msg, "assistant_message", None) or getattr(msg, "content", "")
            if content:
                parts.append(str(content))
    return "\n".join(parts) if parts else ""


def send_message_streaming(
    client: Letta, agent_id: str, user_message: str
) -> Generator:
    """
    Send a message and yield streaming chunks.
    Yields dicts: {type: 'text'|'thinking'|'tool_call'|'tool_return', content: str}
    """
    stream = client.agents.messages.create_stream(
        agent_id=agent_id,
        messages=[{"role": "user", "content": user_message}],
    )

    for chunk in stream:
        if not hasattr(chunk, "message_type"):
            continue

        if chunk.message_type == "reasoning_message":
            yield {"type": "thinking", "content": getattr(chunk, "reasoning", "")}
        elif chunk.message_type == "assistant_message":
            content = getattr(chunk, "assistant_message", None) or getattr(chunk, "content", "")
            yield {"type": "text", "content": str(content)}
        elif chunk.message_type == "tool_call_message":
            tool_name = getattr(chunk, "tool_call", None)
            if tool_name:
                yield {"type": "tool_call", "content": f"Calling: {tool_name.name}"}
        elif chunk.message_type == "tool_return_message":
            yield {"type": "tool_return", "content": getattr(chunk, "tool_return", "")}


def get_conversation_history(client: Letta, agent_id: str, limit: int = 50) -> list:
    """
    Retrieve recent conversation history for display.
    Returns list of dicts: [{role: 'user'|'assistant', content: str}]
    """
    try:
        messages = client.agents.messages.list(agent_id=agent_id, limit=limit)
    except Exception:
        return []

    history = []
    for msg in messages:
        if not hasattr(msg, "message_type"):
            continue
        if msg.message_type == "user_message":
            content = getattr(msg, "content", "")
            if content:
                history.append({"role": "user", "content": str(content)})
        elif msg.message_type == "assistant_message":
            content = getattr(msg, "assistant_message", None) or getattr(msg, "content", "")
            if content:
                history.append({"role": "assistant", "content": str(content)})
    return history
