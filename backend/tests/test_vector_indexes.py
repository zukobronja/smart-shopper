import pytest
from pymongo.errors import OperationFailure

from app.db.indexes import ensure_vector_search_indexes, VECTOR_INDEX_DEFINITIONS


class FakeDatabase:
    def __init__(self, indexes=None):
        self.commands = []
        self.indexes = indexes or []

    async def command(self, payload):
        self.commands.append(payload)
        if "listSearchIndexes" in payload:
            return {"indexes": self.indexes}
        if "createSearchIndexes" in payload:
            index = payload["indexes"][0]
            self.indexes.append({"name": index["name"]})
            return {"ok": 1}
        raise AssertionError("Unexpected command")


@pytest.mark.asyncio
async def test_ensure_vector_search_indexes_creates_missing_indexes():
    db = FakeDatabase()

    await ensure_vector_search_indexes(db)  # type: ignore[arg-type]

    created = [cmd for cmd in db.commands if "createSearchIndexes" in cmd]
    assert len(created) == len(VECTOR_INDEX_DEFINITIONS)


class UnsupportedDatabase(FakeDatabase):
    async def command(self, payload):
        if "listSearchIndexes" in payload:
            raise OperationFailure("not supported")
        return await super().command(payload)


@pytest.mark.asyncio
async def test_ensure_vector_search_indexes_gracefully_handles_missing_feature():
    db = UnsupportedDatabase()
    await ensure_vector_search_indexes(db)  # type: ignore[arg-type]
    # No commands beyond the initial list attempt should be recorded
    assert len(db.commands) == 0
