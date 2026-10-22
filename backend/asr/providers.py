"""Provider selection and model readiness without silent fallback to Mock."""

import asyncio
import importlib.util
import os

STATE = {"ready": False, "status": "not_initialized", "error_code": None}


def provider():
    return os.getenv("ASR_PROVIDER", "mock").strip().lower()


def create_adapter():
    name = provider()
    if name == "mock":
        from .mock import MockASR

        return MockASR()
    if name == "vosk":
        from .vosk_streaming import VoskStreaming

        return VoskStreaming()
    if name == "funasr":
        from .funasr import FunASRStreaming

        return FunASRStreaming()
    raise ValueError("ASR_PROVIDER_UNSUPPORTED")


async def initialize():
    name = provider()
    STATE.update(ready=False, status="loading", error_code=None)
    if name == "mock":
        STATE.update(ready=True, status="mock", error_code=None)
    elif name == "vosk":
        if importlib.util.find_spec("vosk") is None:
            STATE.update(status="unavailable", error_code="ASR_DEPENDENCY_MISSING")
            return
        from .vosk_streaming import load_model

        try:
            await asyncio.to_thread(load_model)
            STATE.update(ready=True, status="ready", error_code=None)
        except FileNotFoundError:
            STATE.update(status="unavailable", error_code="ASR_MODEL_MISSING")
        except Exception:
            STATE.update(status="unavailable", error_code="ASR_MODEL_LOAD_FAILED")
    elif name == "funasr":
        # Session creation still attempts real initialization; health does not
        # label a configured but untested model as ready.
        STATE.update(status="load_on_session", error_code=None)
    else:
        STATE.update(status="unavailable", error_code="ASR_PROVIDER_UNSUPPORTED")


def capabilities():
    name = provider()
    return {
        "provider": name,
        **STATE,
        "mode": "mock" if name == "mock" else "streaming",
        "native_hotwords": False,
        "sample_rate": 16000,
        "supports_partial": True,
        "supports_endpoint_final": name == "vosk",
        "model": os.getenv("ASR_MODEL")
        or ("vosk-model-small-cn-0.22" if name == "vosk" else None),
    }
