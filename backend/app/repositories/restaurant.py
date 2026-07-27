"""Repository interfaces (PostgreSQL persistence planned; in-memory for MVP)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import Restaurant


class RestaurantRepository(ABC):
    @abstractmethod
    async def upsert_many(self, restaurants: list[Restaurant]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, restaurant_id: str) -> Restaurant | None:
        raise NotImplementedError


class InMemoryRestaurantRepository(RestaurantRepository):
    def __init__(self) -> None:
        self._store: dict[str, Restaurant] = {}

    async def upsert_many(self, restaurants: list[Restaurant]) -> None:
        for r in restaurants:
            self._store[r.restaurant_id] = r

    async def get_by_id(self, restaurant_id: str) -> Restaurant | None:
        return self._store.get(restaurant_id)
