from typing import Protocol

class LLMProvider(Protocol):
    async def extract(self, final_segments: list[dict], schema: dict) -> dict: ...

class RetrievalProvider(Protocol):
    async def search(self, query: str, limit: int = 5) -> list[dict]: ...
