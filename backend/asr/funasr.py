import asyncio
from .base import ASRAdapter, ASRResult


class FunASRStreaming(ASRAdapter):
    """Optional CPU/GPU Paraformer online model. Model shared; cache per session."""

    model = None
    lock = None

    async def start_session(self, hotwords):
        if type(self).model is None:
            from funasr import AutoModel
            import os

            type(self).model = await asyncio.to_thread(
                AutoModel,
                model=os.getenv("ASR_MODEL", "paraformer-zh-streaming"),
                disable_update=True,
            )
            type(self).lock = asyncio.Lock()
        self.cache, self.pending, self.text = {}, bytearray(), ""

    async def _infer(self, data, final):
        import numpy as np

        async with type(self).lock:
            result = await asyncio.to_thread(
                self.model.generate,
                input=np.frombuffer(data, dtype="<i2").astype("float32") / 32768,
                cache=self.cache,
                is_final=final,
                chunk_size=[0, 10, 5],
                encoder_chunk_look_back=4,
                decoder_chunk_look_back=1,
            )
        if result:
            self.text += result[0].get("text", "")

    async def send_audio_chunk(self, pcm):
        self.pending.extend(pcm)
        while len(self.pending) >= 19200:
            data = bytes(self.pending[:19200])
            del self.pending[:19200]
            await self._infer(data, False)

    async def get_partial_result(self):
        return ASRResult(self.text, False) if self.text else None

    async def finalize_segment(self):
        await self._infer(bytes(self.pending) or b"\x00\x00" * 960, True)
        self.pending.clear()
        return ASRResult(self.text, True) if self.text else None

    async def end_session(self):
        self.cache.clear()
        self.pending.clear()
