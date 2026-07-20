import asyncio

from server.auth.service import AuthService, InvalidCredentialsError
from server.db.connection import create_connection
from server.db.schema import init_schema
from server.db.users_repository import UsernameTakenError, UsersRepository


def _service() -> AuthService:
    conn = create_connection(":memory:")
    init_schema(conn)
    return AuthService(UsersRepository(conn))


def _run(coro):
    return asyncio.run(coro)


class TestRegister:
    def test_register_creates_a_user_with_default_elo(self):
        service = _service()
        user = _run(service.register("alice", "hunter2"))
        assert user.username == "alice"
        assert user.elo == 1200

    def test_register_rejects_a_duplicate_username(self):
        service = _service()
        _run(service.register("alice", "hunter2"))
        try:
            _run(service.register("alice", "different-password"))
            assert False, "expected UsernameTakenError"
        except UsernameTakenError:
            pass


class TestLogin:
    def test_login_succeeds_with_the_right_password(self):
        service = _service()
        _run(service.register("alice", "hunter2"))
        user = _run(service.login("alice", "hunter2"))
        assert user.username == "alice"

    def test_login_rejects_the_wrong_password(self):
        service = _service()
        _run(service.register("alice", "hunter2"))
        try:
            _run(service.login("alice", "wrong-password"))
            assert False, "expected InvalidCredentialsError"
        except InvalidCredentialsError:
            pass

    def test_login_rejects_an_unknown_username(self):
        service = _service()
        try:
            _run(service.login("nobody", "whatever"))
            assert False, "expected InvalidCredentialsError"
        except InvalidCredentialsError:
            pass
