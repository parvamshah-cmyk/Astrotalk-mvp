"""
setup_agent.py

One-time script to register custom tools and create a template agent
on the Letta server. Run this AFTER docker-compose is up.

Usage:
    python scripts/setup_agent.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from letta_client import Letta

from tools.mongo_tools import fetch_user_birth_details, save_user_birth_details

load_dotenv()

LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://localhost:8283")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "letta/letta-free")
SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "system_prompt.txt"
)


def load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, "r") as f:
        return f.read().strip()


def main():
    print(f"Connecting to Letta server at {LETTA_BASE_URL}...")
    client = Letta(base_url=LETTA_BASE_URL)
    print("Connected.")

    # Register custom tools (upsert = create or update)
    print("Registering tools...")
    fetch_tool = client.tools.upsert_from_function(
        func=fetch_user_birth_details,
        tags=["astrotalk", "mongodb"],
        pip_requirements=[{"name": "pymongo"}],
    )
    print(f"  -> {fetch_tool.name} (id={fetch_tool.id})")

    save_tool = client.tools.upsert_from_function(
        func=save_user_birth_details,
        tags=["astrotalk", "mongodb"],
        pip_requirements=[{"name": "pymongo"}],
    )
    print(f"  -> {save_tool.name} (id={save_tool.id})")

    # Load system prompt
    system_prompt = load_system_prompt()
    print(f"Loaded system prompt ({len(system_prompt)} chars)")

    # Create template agent
    print("Creating template agent...")
    agent = client.agents.create(
        name="astrotalk-template",
        description="AstroTalk AI Astrologer - template agent",
        model=LLM_MODEL,
        embedding=EMBEDDING_MODEL,
        system=system_prompt,
        memory_blocks=[
            {
                "label": "persona",
                "value": (
                    "I am an expert Vedic and Western astrologer from AstroTalk. "
                    "I provide insightful, compassionate, and personalized "
                    "astrological readings based on the user's birth chart. "
                    "I always check for existing birth details before asking. "
                    "I speak warmly and explain astrological terms simply."
                ),
                "limit": 5000,
            },
            {
                "label": "human",
                "value": "No user details known yet. Need to fetch or collect birth information.",
                "limit": 3000,
                "description": (
                    "Information about the current user. Contains user_id, name, "
                    "date of birth, time of birth, place of birth, and any other "
                    "relevant facts learned during conversations."
                ),
            },
            {
                "label": "astro_context",
                "value": "No birth chart computed yet. Awaiting birth details.",
                "limit": 5000,
                "description": (
                    "Astrological context for the current user. Update this with "
                    "computed birth chart data, planetary positions, dashas, "
                    "and key insights from readings."
                ),
            },
        ],
        tool_ids=[fetch_tool.id, save_tool.id],
        include_base_tools=True,
        tags=["astrotalk"],
    )
    print(f"Created agent: {agent.name} (id={agent.id})")
    print()
    print("Setup complete! You can now run the Streamlit app.")
    print(f"  Tool IDs: fetch={fetch_tool.id}, save={save_tool.id}")
    print(f"  Agent ID: {agent.id}")

    return agent


if __name__ == "__main__":
    main()
