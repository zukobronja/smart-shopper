#!/usr/bin/env python3
"""Quick connectivity check against the SmartShopper MongoDB cluster.

Usage:
    python scripts/check_mongo_connection.py

Environment variables (defaults provided for the Tavily demo cluster):
    MONGO_USER, MONGO_PASS, MONGO_CLUSTER_URL, DATABASE_NAME

The script attempts a ping, prints the collection list, and exits with a
non-zero status if the connection fails. Intended for manual diagnostics.
"""

from __future__ import annotations

import asyncio
import os
from typing import Sequence

from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.errors import PyMongoError


def build_connection_string() -> str:
    user = os.getenv("MONGO_USER", "tavily_demo")
    password = os.getenv("MONGO_PASS", "mUg2ApcYmmDfJqio")
    cluster = os.getenv("MONGO_CLUSTER_URL", "tavily-demo.v9wwnlb.mongodb.net")
    return f"mongodb+srv://{user}:{password}@{cluster}/?retryWrites=true&w=majority"


async def main() -> None:
    mongo_uri = build_connection_string()
    database_name = os.getenv("DATABASE_NAME", "smartshopper")

    print("Connecting to:", mongo_uri)
    print("Target database:", database_name)

    client = AsyncMongoClient(mongo_uri)
    try:
        await client.admin.command("ping")
        print("Ping successful.")

        db = client[database_name]
        collections: Sequence[str] = await db.list_collection_names()
        print("Collections:")
        for name in collections:
            print(f"  - {name}")
    except PyMongoError as exc:  # pragma: no cover - network dependent
        print("Connection failed:", exc)
        raise SystemExit(1) from exc
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
