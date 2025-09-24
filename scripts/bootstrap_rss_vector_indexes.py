#!/usr/bin/env python3
"""Create Atlas Search vector indexes required for RSS retrieval."""

import argparse
import asyncio
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"

backend_path_str = str(BACKEND_PATH)
if backend_path_str not in sys.path:
    sys.path.insert(0, backend_path_str)

from pymongo.errors import OperationFailure

from app.config import settings
from app.db.client import connect_to_mongo, close_mongo_connection, mongo_client
from app.db.indexes import VECTOR_INDEX_DEFINITIONS


async def drop_search_index(name: str) -> None:
    try:
        await mongo_client.database.command(
            {"dropSearchIndex": "rss_items", "index": name}
        )
        print(f"Dropped existing search index: {name}")
    except OperationFailure as exc:
        if "index not found" in str(exc).lower():
            print(f"Search index {name} did not exist")
        else:
            raise


async def create_search_index(name: str, field: str, dimensions: int, similarity: str) -> None:
    definition = {
        "mappings": {
            "dynamic": False,
            "fields": {
                field: {
                    "type": "vector",
                    "dimensions": dimensions,
                    "similarity": similarity,
                }
            },
        }
    }
    payload = {
        "createSearchIndexes": "rss_items",
        "indexes": [
            {
                "name": name,
                "definition": definition,
            }
        ],
    }
    await mongo_client.database.command(payload)
    print(f"Created search index: {name} ({field}, dim={dimensions})")


async def bootstrap(force: bool, only: Sequence[str]) -> None:
    await connect_to_mongo()
    try:
        selected = [idx for idx in VECTOR_INDEX_DEFINITIONS if not only or idx["name"] in only]
        if not selected:
            print("No matching indexes to process. Exiting.")
            return

        for definition in selected:
            name = definition["name"]
            field = definition["field"]
            dimensions = definition["dimensions"]
            similarity = definition["similarity"]

            if force:
                await drop_search_index(name)

            try:
                await create_search_index(name, field, dimensions, similarity)
            except OperationFailure as exc:
                if "index already exists" in str(exc).lower():
                    print(f"Search index {name} already exists; skipping")
                else:
                    raise
    finally:
        await close_mongo_connection()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap Atlas Search vector indexes for RSS items",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop and recreate the indexes even if they exist",
    )
    parser.add_argument(
        "--index",
        dest="indexes",
        action="append",
        help="Name of a specific index to manage (can be repeated)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Environment:", settings.ENVIRONMENT)
    print("Target database:", settings.DATABASE_NAME)
    asyncio.run(bootstrap(force=args.force, only=args.indexes or ()))


if __name__ == "__main__":
    main()
