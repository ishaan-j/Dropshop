"""Shared test setup for every backend package. Run from backend/:  python -m pytest

No test may reach a real MongoDB cluster or Tiger Data service, whatever is in your .env:
creating either client raises. Tests that need Mongo ask for `fake_mongo`, an in-process stand-in
that supports the handful of operations `data/mongo.py` uses. With Tiger Data refused, the
database store keeps prices in its own process, which is what those tests run on.
"""

from datetime import datetime

import pytest

from data import mongo, timescale


def _as_bson(doc: dict) -> dict:
    """Mongo keeps dates to the millisecond; do the same so tests see what production sees."""
    return {
        k: v.replace(microsecond=v.microsecond // 1000 * 1000) if isinstance(v, datetime) else v
        for k, v in doc.items()
    }


class FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    def sort(self, keys):
        for key, direction in reversed(keys):  # stable sorts, last key first
            self._docs.sort(key=lambda d: d[key], reverse=direction < 0)
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    async def to_list(self) -> list[dict]:
        return [dict(d) for d in self._docs]


class FakeCollection:
    def __init__(self):
        self.docs: list[dict] = []
        self.indexes: list[tuple] = []
        self._inserted = 0

    def _match(self, query: dict) -> list[dict]:
        return [d for d in self.docs if all(d.get(k) == v for k, v in query.items())]

    def find(self, query: dict | None = None) -> FakeCursor:
        return FakeCursor(self._match(query or {}))

    async def find_one(self, query: dict) -> dict | None:
        found = self._match(query)
        return dict(found[0]) if found else None

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
        found = self._match(query)
        if found:
            found[0].update(_as_bson(update["$set"]))
        elif upsert:
            self.docs.append({**query, **_as_bson(update["$set"])})

    async def insert_one(self, doc: dict) -> None:
        self._inserted += 1  # like an ObjectId: later inserts sort after earlier ones
        self.docs.append({"_id": self._inserted, **_as_bson(doc)})

    async def delete_many(self, query: dict) -> None:
        gone = {id(d) for d in self._match(query)}
        self.docs = [d for d in self.docs if id(d) not in gone]

    async def create_index(self, keys, unique: bool = False) -> None:
        self.indexes.append((tuple(keys), unique))


class FakeDatabase:
    name = "dropshot_test"

    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self._collections.setdefault(name, FakeCollection())


@pytest.fixture(autouse=True)
def no_real_mongo(monkeypatch):
    def refuse():
        raise RuntimeError("Tests must not connect to MongoDB. Use the fake_mongo fixture.")

    monkeypatch.setattr(mongo, "client", refuse)


@pytest.fixture(autouse=True)
def no_real_tiger(monkeypatch):
    def refuse():
        raise timescale.TigerUnavailable("Tests must not connect to Tiger Data.")

    monkeypatch.setattr(timescale, "_get_pool", refuse)


@pytest.fixture
def fake_mongo(monkeypatch) -> FakeDatabase:
    database = FakeDatabase()
    monkeypatch.setattr(mongo, "db", lambda: database)
    return database
