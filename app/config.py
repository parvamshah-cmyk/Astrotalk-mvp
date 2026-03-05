"""
Central configuration loaded from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Letta
LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://localhost:8283")

# Models
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "letta/letta-free")

# MongoDB (host-side access)
MONGO_USER = os.getenv("MONGO_USER", "astrotalk")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "astrotalk123")
MONGO_HOST = os.getenv("MONGO_HOST_EXTERNAL", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DB = os.getenv("MONGO_DB", "astrotalk")

# System prompt path
SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "system_prompt.txt"
)
