import asyncio

from server.db.connection import create_connection
from server.db.schema import init_schema
from server.db.users_repository import UsernameTakenError, UsersRepository


def _repo() -> UsersRepository:
    conn = create_connection(":memory:")
    init_schema(conn)
    return UsersRepository(conn)


def _run(coro):
    return asyncio.run(coro)


class TestCreate:
    def test_create_returns_a_user_record_with_default_elo(self):
        repo = _repo()
        user = _run(repo.create("alice", "hash", "salt"))
        assert user.username == "alice"
        assert user.elo == 1200
        assert user.id is not None

    def test_duplicate_username_raises(self):
        repo = _repo()
        _run(repo.create("alice", "hash", "salt"))
        try:
            _run(repo.create("alice", "otherhash", "othersalt"))
            assert False, "expected UsernameTakenError"
        except UsernameTakenError:
            pass


class TestGet:
    def test_get_by_username_returns_none_when_missing(self):
        repo = _repo()
        assert _run(repo.get_by_username("nobody")) is None

    def test_get_by_username_finds_a_created_user(self):
        repo = _repo()
        created = _run(repo.create("bob", "hash", "salt"))
        found = _run(repo.get_by_username("bob"))
        assert found == created

    def test_get_by_id_finds_a_created_user(self):
        repo = _repo()
        created = _run(repo.create("carol", "hash", "salt"))
        found = _run(repo.get_by_id(created.id))
        assert found == created

    def test_get_by_id_returns_none_when_missing(self):
        repo = _repo()
        assert _run(repo.get_by_id(999)) is None


class TestUpdateElo:
    def test_update_elo_persists(self):
        repo = _repo()
        created = _run(repo.create("dave", "hash", "salt"))
        _run(repo.update_elo(created.id, 1300))
        updated = _run(repo.get_by_id(created.id))
        assert updated.elo == 1300
