from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ASRResult:
    text: str
    is_final: bool
    start_time: float | None = None
    end_time: float | None = None
    confidence: float | None = None
    raw_text: str | None = None
    radio_digits: dict | None = None


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


class ASRError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
