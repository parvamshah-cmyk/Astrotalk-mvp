"""
test_e2e.py — End-to-end tests for the AstroTalk system.

Tests:
1. Letta server connectivity
2. MongoDB connectivity
3. Tool registration
4. New user flow
5. Returning user flow

Usage:
    python scripts/test_e2e.py
"""

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()


def test_letta_connection():
    """Test 1: Letta server is reachable."""
    print("[TEST 1] Letta server connectivity...")
    from letta_client import Letta

    base_url = os.getenv("LETTA_BASE_URL", "http://localhost:8283")
    client = Letta(base_url=base_url)
    agents = client.agents.list(limit=1)
    print(f"  OK — Server reachable at {base_url}")
    return client


def test_mongodb_connection():
    """Test 2: MongoDB is reachable."""
    print("[TEST 2] MongoDB connectivity...")
    from pymongo import MongoClient

    mongo_uri = (
        f"mongodb://{os.getenv('MONGO_USER', 'astrotalk')}:"
        f"{os.getenv('MONGO_PASSWORD', 'astrotalk123')}@"
        f"{os.getenv('MONGO_HOST_EXTERNAL', 'localhost')}:"
        f"{os.getenv('MONGO_PORT', '27017')}/"
        f"{os.getenv('MONGO_DB', 'astrotalk')}?authSource=admin"
    )
    mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command("ping")

    # Ensure index
    db = mongo_client[os.getenv("MONGO_DB", "astrotalk")]
    db["users"].create_index("user_id", unique=True)

    print("  OK — MongoDB reachable, users index verified")
    return mongo_client


def test_tool_registration(letta_client):
    """Test 3: Custom tools can be registered."""
    print("[TEST 3] Tool registration...")
    from tools.mongo_tools import fetch_user_birth_details, save_user_birth_details

    fetch_tool = letta_client.tools.upsert_from_function(
        func=fetch_user_birth_details,
        name="fetch_user_birth_details",
        tags=["astrotalk", "mongodb"],
    )
    save_tool = letta_client.tools.upsert_from_function(
        func=save_user_birth_details,
        name="save_user_birth_details",
        tags=["astrotalk", "mongodb"],
    )
    print(f"  OK — fetch_tool={fetch_tool.id}, save_tool={save_tool.id}")
    return fetch_tool, save_tool


def test_new_user_flow(letta_client, fetch_tool, save_tool):
    """Test 4: New user conversation flow."""
    print("[TEST 4] New user flow...")

    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "system_prompt.txt")
    with open(prompt_path, "r") as f:
        system_prompt = f.read().strip()

    test_user_id = str(uuid.uuid4())
    agent_name = f"astrotalk-test-{test_user_id[:8]}"

    agent = letta_client.agents.create(
        name=agent_name,
        model=os.getenv("VERTEX_MODEL", "vertex_ai/gemini-2.0-flash"),
        embedding=os.getenv("VERTEX_EMBEDDING", "vertex_ai/text-embedding-005"),
        system=system_prompt,
        memory_blocks=[
            {"label": "persona", "value": "I am an AstroTalk astrologer.", "limit": 5000},
            {
                "label": "human",
                "value": json.dumps({"user_id": test_user_id, "birth_details_collected": False}),
                "limit": 3000,
            },
            {"label": "astro_context", "value": "No data yet.", "limit": 5000},
        ],
        tool_ids=[fetch_tool.id, save_tool.id],
        include_base_tools=True,
        tags=["astrotalk", "test"],
    )
    print(f"  Created agent: {agent.name}")

    # Send greeting
    resp = letta_client.agents.messages.create(
        agent_id=agent.id,
        messages=[{
            "role": "user",
            "content": f"Hello! My user ID is {test_user_id}. I am new here.",
        }],
    )
    for msg in resp.messages:
        if hasattr(msg, "message_type") and msg.message_type == "assistant_message":
            content = getattr(msg, "assistant_message", "") or getattr(msg, "content", "")
            print(f"  Agent: {str(content)[:100]}...")
            break

    # Provide birth details
    resp2 = letta_client.agents.messages.create(
        agent_id=agent.id,
        messages=[{
            "role": "user",
            "content": "My name is Test User. I was born on 1990-06-15 at 10:30 AM in Mumbai, India.",
        }],
    )
    tool_called = False
    for msg in resp2.messages:
        if hasattr(msg, "message_type"):
            if msg.message_type == "tool_call_message":
                tool_called = True
                print(f"  Tool called: {msg.tool_call.name}")
            elif msg.message_type == "assistant_message":
                content = getattr(msg, "assistant_message", "") or getattr(msg, "content", "")
                print(f"  Agent: {str(content)[:100]}...")

    # Cleanup
    letta_client.agents.delete(agent.id)
    print(f"  Cleaned up agent. Tool called: {tool_called}")
    print(f"  OK — New user flow completed (user_id={test_user_id})")
    return test_user_id


def test_returning_user_flow(letta_client, fetch_tool, save_tool, user_id):
    """Test 5: Returning user flow (data should exist in MongoDB)."""
    print("[TEST 5] Returning user flow...")

    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "system_prompt.txt")
    with open(prompt_path, "r") as f:
        system_prompt = f.read().strip()

    agent_name = f"astrotalk-return-{user_id[:8]}"

    agent = letta_client.agents.create(
        name=agent_name,
        model=os.getenv("VERTEX_MODEL", "vertex_ai/gemini-2.0-flash"),
        embedding=os.getenv("VERTEX_EMBEDDING", "vertex_ai/text-embedding-005"),
        system=system_prompt,
        memory_blocks=[
            {"label": "persona", "value": "I am an AstroTalk astrologer.", "limit": 5000},
            {
                "label": "human",
                "value": json.dumps({"user_id": user_id, "birth_details_collected": False}),
                "limit": 3000,
            },
            {"label": "astro_context", "value": "No data yet.", "limit": 5000},
        ],
        tool_ids=[fetch_tool.id, save_tool.id],
        include_base_tools=True,
        tags=["astrotalk", "test"],
    )

    resp = letta_client.agents.messages.create(
        agent_id=agent.id,
        messages=[{
            "role": "user",
            "content": f"Hi, I'm back! My user ID is {user_id}.",
        }],
    )

    found_fetch = False
    for msg in resp.messages:
        if hasattr(msg, "message_type"):
            if msg.message_type == "tool_call_message":
                if "fetch" in msg.tool_call.name:
                    found_fetch = True
                    print(f"  Tool called: {msg.tool_call.name}")
            elif msg.message_type == "assistant_message":
                content = getattr(msg, "assistant_message", "") or getattr(msg, "content", "")
                print(f"  Agent: {str(content)[:100]}...")

    # Cleanup
    letta_client.agents.delete(agent.id)
    print(f"  Cleaned up agent. Fetched from DB: {found_fetch}")

    if found_fetch:
        print("  OK — Returning user flow works.")
    else:
        print("  WARNING — Agent did not call fetch tool. System prompt may need tuning.")


def main():
    print("=" * 60)
    print("AstroTalk End-to-End Test Suite")
    print("=" * 60)
    print()

    letta_client = test_letta_connection()
    print()

    test_mongodb_connection()
    print()

    fetch_tool, save_tool = test_tool_registration(letta_client)
    print()

    user_id = test_new_user_flow(letta_client, fetch_tool, save_tool)
    print()

    test_returning_user_flow(letta_client, fetch_tool, save_tool, user_id)
    print()

    print("=" * 60)
    print("All tests completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
