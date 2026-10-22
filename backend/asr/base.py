from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ASRResult:
    text: str
    is_final: bool


class ASRAdapter(ABC):
    native_hotwords = False

    @abstractmethod
    async def start_session(self, hotwords: list[str]): ...
    @abstractmethod
    async def send_audio_chunk(self, pcm: bytes): ...
    @abstractmethod
    async def get_partial_result(self) -> ASRResult | None: ...
    @abstractmethod
    async def finalize_segment(self) -> ASRResult | None: ...
    @abstractmethod
    async def end_session(self): ...
