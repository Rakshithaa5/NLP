"""
db.py — Supabase client singleton.

Reads SUPABASE_URL and SUPABASE_ANON_KEY from the environment (.env).
All service modules import `get_client()` to get the shared client.

Phase 0: client initialisation + trivial connectivity ping.
"""

import os
from supabase import create_client, Client

_client: Client | None = None


def get_client() -> Client:
    """Return the shared Supabase client, creating it on first call."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_ANON_KEY", "")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env"
            )
        _client = create_client(url, key)
    return _client
