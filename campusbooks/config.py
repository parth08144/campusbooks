"""
config.py – CampusBooks
=======================
Central configuration module.

WHY: Keeping the database connection in one place means every other script
imports `get_db()` instead of hard-coding the URI. Switching from local
MongoDB to Atlas only requires changing the .env file.

WHY python-dotenv: It loads .env into os.environ at import time, so secrets
never touch the source code (important for Git repositories).
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load variables from .env into the process environment.
# override=False means real env vars win over .env (good for CI/CD pipelines).
load_dotenv(override=False)

# Pull values with sensible defaults so the project works out-of-the-box
# with a local MongoDB instance even without a .env file.
MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME: str   = os.getenv("DB_NAME",   "campusbooks")


def get_db():
    """
    Return a (client, db) tuple.

    WHY return both? The caller can close the client explicitly after a
    batch job, preventing connection leaks in long-running scripts.

    Usage:
        client, db = get_db()
        # … do work …
        client.close()
    """
    client = MongoClient(MONGO_URI)
    db     = client[DB_NAME]
    return client, db


# ── Quick connection test (run this file directly to verify connectivity) ──
if __name__ == "__main__":
    client, db = get_db()
    try:
        # ping is the lightest possible round-trip to the server
        client.admin.command("ping")
        print(f"✅  Connected to MongoDB | URI: {MONGO_URI} | DB: {DB_NAME}")
    except Exception as exc:
        print(f"❌  Connection failed: {exc}")
    finally:
        client.close()
