from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Generic repository interface — swap SQLite for PostgreSQL without touching services."""

    @abstractmethod
    async def get_by_id(self, id: str) -> T | None:
        ...

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        ...

    @abstractmethod
    async def delete(self, id: str) -> bool:
        ...

    @abstractmethod
    async def count(self) -> int:
        ...
