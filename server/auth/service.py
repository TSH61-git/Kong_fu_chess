# Orchestrates register/login: calls hashing.py + a UsersRepository only.
from __future__ import annotations

from server.auth.hashing import hash_password, verify_password
from server.db.users_repository import UserRecord, UsernameTakenError, UsersRepository

__all__ = ["AuthService", "InvalidCredentialsError", "UsernameTakenError"]


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, users_repo: UsersRepository) -> None:
        self.users_repo = users_repo

    async def register(self, username: str, password: str) -> UserRecord:
        password_hash, salt = hash_password(password)
        return await self.users_repo.create(username, password_hash, salt)

    async def login(self, username: str, password: str) -> UserRecord:
        user = await self.users_repo.get_by_username(username)
        if user is None or not verify_password(password, user.salt, user.password_hash):
            raise InvalidCredentialsError(username)
        return user
