from .base import ASRAdapter, ASRResult

class MockASR(ASRAdapter):
    """Deterministic transport demo. Never represents audio content."""
    async def start_session(self, hotwords):
        self.samples = 0
        self.closed = False

    async def send_audio_chunk(self, pcm):
        self.samples += len(pcm) // 2

    async def get_partial_result(self):
        return ASRResult(f'【模拟识别】已接收音频 {self.samples / 16000:.1f} 秒', False)

    async def finalize_segment(self):
        return ASRResult(f'【模拟识别】音频链路演示，共 {self.samples / 16000:.1f} 秒（非真实转写）', True) if self.samples else None

    async def end_session(self):
        self.closed = True
