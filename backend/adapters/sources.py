from dataclasses import dataclass
from typing import Protocol, AsyncIterator


@dataclass
class AudioChunk:
    source_id: str
    sample_rate: int
    timestamp: float
    data: bytes


class AudioSource(Protocol):
    source_id: str
    group: str
    priority: int

    def stream(self) -> AsyncIterator[AudioChunk]: ...


class UploadedFileAudioSource:
    source_id: str
    group = "uploaded"
    priority = 0


class MicrophoneAudioSource(AudioSource, Protocol):
    pass


class VHFAudioSource(AudioSource, Protocol):
    pass


class RadioGatewayAudioSource(AudioSource, Protocol):
    pass


class SIPRTPAudioSource(AudioSource, Protocol):
    pass
