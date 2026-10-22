import asyncio
import json
import os
import time
import uuid
import math
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from backend.models import DATA, save, get, listing, remove
from backend.audio.codec import decode
from backend.asr.base import ASRError
from backend.asr.providers import initialize, capabilities, create_adapter
from backend.events.extract import extract
from backend.asr.radio_digits import profile as digit_profile
from backend.review.api import router as review_router
from backend.review.service import (
    commit_revision,
    current_text,
    fingerprint,
    segment as review_segment,
)


@asynccontextmanager
async def lifespan(app):
    await initialize()
    yield


app = FastAPI(title="llmErV", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(review_router)

PROVIDER = os.getenv("ASR_PROVIDER", "mock").strip().lower()
MAX_BYTES = 50 * 1024 * 1024


@app.get("/asr/radio-digits")
def radio_digit_profile():
    return digit_profile()


@app.get("/health")
def health():
    info = capabilities()
    name = info["provider"]
    return {
        "status": "ok",
        "asr_provider": name,
        "mode": "模拟识别"
        if name == "mock"
        else ("真实流式识别 · " + name if info["ready"] else "ASR 未就绪"),
        "asr": info,
        "native_hotwords": False,
        "llm_provider": "rules",
    }


@app.get("/asr/capabilities")
def asr_capabilities():
    return capabilities()


@app.post("/audio", status_code=201)
async def upload(file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".mp4"}:
        raise HTTPException(415, "UNSUPPORTED_FORMAT")
    id = str(uuid.uuid4())
    raw, wav = DATA / f"{id}.input{suffix}", DATA / f"{id}.wav"
    size = 0
    try:
        with raw.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "FILE_TOO_LARGE")
                out.write(chunk)
        metadata = await asyncio.to_thread(decode, raw, wav)
        item = {"id": id, "name": Path(file.filename).name, "size": size, **metadata}
        save("audio", id, item)
        return item
    except HTTPException:
        wav.unlink(missing_ok=True)
        raise
    except Exception:
        wav.unlink(missing_ok=True)
        raise HTTPException(422, "INVALID_AUDIO_OR_DURATION")
    finally:
        raw.unlink(missing_ok=True)
        await file.close()


@app.get("/audio")
def audio_list(q: str = ""):
    return [x for x in listing("audio") if q.lower() in x["name"].lower()]


@app.get("/audio/{id}/content")
def content(id: str):
    if not any(item["id"] == id for item in listing("audio")):
        raise HTTPException(404, "AUDIO_NOT_FOUND")
    return FileResponse(DATA / f"{id}.wav", media_type="audio/wav")


@app.delete("/audio/{id}", status_code=204)
def delete(id: str):
    if not any(item["id"] == id for item in listing("audio")):
        raise HTTPException(404, "AUDIO_NOT_FOUND")
    remove(id)
    (DATA / f"{id}.wav").unlink(missing_ok=True)


@app.get("/sessions")
def sessions():
    return listing("session")


@app.get("/sessions/{id}/transcripts")
def transcripts(id: str):
    return sorted(
        [x for x in listing("transcript") if x["session_id"] == id],
        key=lambda x: (x["start_time"], x["end_time"], x["segment_id"]),
    )


@app.get("/events")
def events(session_id: str | None = None):
    # Derive from current text so older deployments' stale events are repaired
    # on read, and removed/revised facts cannot remain in the sidebar.
    return [
        extract(item)
        for item in sorted(
            listing("transcript"),
            key=lambda x: (x["start_time"], x["end_time"], x["segment_id"]),
        )
        if session_id is None or item["session_id"] == session_id
    ]


class Revision(BaseModel):
    text: str = Field(max_length=10000)


@app.patch("/transcripts/{id}")
def revise(id: str, body: Revision):
    item = review_segment(id)
    return commit_revision(
        id, fingerprint(current_text(item)), body.text, "manual_edit"
    )


class Words(BaseModel):
    words: list[str] = Field(max_length=500)


@app.get("/hotwords")
def hotwords():
    return get("hotwords") or {
        "words": [
            "塔台",
            "机坪",
            "消防",
            "医疗",
            "公安",
            "应急救援",
            "紧急撤离",
            "跑道入侵",
            "起火",
            "烟雾",
            "漏油",
            "人员受伤",
            "集结点",
            "救援车辆",
        ],
        "mode": "dictionary_only",
        "native_supported": False,
    }


@app.put("/hotwords")
def set_hotwords(body: Words):
    if any(not w.strip() or len(w) > 80 for w in body.words):
        raise HTTPException(422, "INVALID_HOTWORD")
    value = {
        "words": list(dict.fromkeys(body.words)),
        "mode": "dictionary_only",
        "native_supported": False,
    }
    save("dictionary", "hotwords", value)
    return value


@app.websocket("/ws/recognize")
async def recognize(ws: WebSocket):
    await ws.accept()
    adapter = None
    sid, segment_id = str(uuid.uuid4()), str(uuid.uuid4())
    state, samples, seq = "new", 0, 0
    segment_start = 0.0
    source = None
    recognition_mode = "general"
    audio_offset = 0.0
    max_samples = 16000 * 1800

    async def error(code):
        await ws.send_json({"type": "error", "code": code})

    async def emit_result(result):
        nonlocal segment_id, segment_start
        if result is None:
            return
        item = {
            "type": "final" if result.is_final and result.text else "partial",
            "session_id": sid,
            "source_id": source,
            "segment_id": segment_id,
            "start_time": audio_offset
            + (result.start_time if result.start_time is not None else segment_start),
            "end_time": audio_offset
            + (result.end_time if result.end_time is not None else samples / 16000),
            "text": result.text,
            "is_final": bool(result.is_final and result.text),
            "asr_engine": PROVIDER,
            "confidence": result.confidence,
            "speaker_id": None,
            "recognition_mode": recognition_mode,
            "radio_digits": result.radio_digits,
        }
        if item["is_final"]:
            item.update(
                original_text=result.raw_text
                if result.raw_text is not None
                else result.text,
                corrected_text=result.text,
            )
            save("transcript", segment_id, item)
            event = extract(item)
            save("event", segment_id + ":event", event)
            await ws.send_json(item)
            await ws.send_json({"type": "event", **event})
        else:
            await ws.send_json(item)
        if result.is_final:
            segment_id = str(uuid.uuid4())
            segment_start = samples / 16000

    try:
        message = await asyncio.wait_for(ws.receive_json(), 15)
        source = message.get("source_id")
        if (
            message.get("type") != "start"
            or not source
            or not any(item["id"] == source for item in listing("audio"))
        ):
            await error("INVALID_START")
            return
        try:
            recognition_mode = message.get("recognition_mode", "general")
            offset = message.get("audio_offset", 0)
            audio = next(item for item in listing("audio") if item["id"] == source)
            if (
                isinstance(offset, bool)
                or not isinstance(offset, (int, float))
                or not math.isfinite(offset)
                or offset < 0
                or offset >= audio["duration"]
                or (recognition_mode != "radio_digits" and offset != 0)
            ):
                await error("INVALID_AUDIO_OFFSET")
                return
            audio_offset = float(offset)
            if recognition_mode == "radio_digits":
                max_samples = min(
                    30 * 16000, math.ceil((audio["duration"] - audio_offset) * 16000)
                )
            adapter = (
                create_adapter()
                if recognition_mode == "general"
                else create_adapter(recognition_mode)
            )
        except ValueError:
            await error("PROVIDER_UNAVAILABLE")
            return
        if PROVIDER != "mock":
            await ws.send_json(
                {"type": "model_status", "status": "loading", "asr_engine": PROVIDER}
            )
        await adapter.start_session(hotwords()["words"])
        state = "running"
        save(
            "session",
            sid,
            {
                "id": sid,
                "source_id": source,
                "status": state,
                "asr_engine": PROVIDER,
                "recognition_mode": recognition_mode,
                "audio_offset": audio_offset,
            },
        )
        await ws.send_json(
            {
                "type": "ready",
                "session_id": sid,
                "asr_engine": PROVIDER,
                "sample_rate": 16000,
                "resume_supported": False,
                "recognition_mode": recognition_mode,
            }
        )
        while True:
            packet = await asyncio.wait_for(ws.receive(), 120)
            if packet["type"] == "websocket.disconnect":
                state = "disconnected"
                break
            if packet.get("bytes") is not None:
                pcm = packet["bytes"]
                if state != "running":
                    await error("INVALID_STATE")
                    continue
                if not pcm or len(pcm) % 2 or len(pcm) > 64000:
                    await error("INVALID_CHUNK")
                    continue
                if samples + len(pcm) // 2 > max_samples:
                    await error("SESSION_TOO_LONG")
                    break
                started = time.perf_counter()
                await adapter.send_audio_chunk(pcm)
                samples += len(pcm) // 2
                result = await adapter.get_partial_result()
                elapsed = time.perf_counter() - started
                seq += 1
                await emit_result(result)
                await ws.send_json(
                    {
                        "type": "progress",
                        "sequence": seq,
                        "audio_time": audio_offset + samples / 16000,
                        "inference_ms": elapsed * 1000,
                        "rtf": elapsed / (len(pcm) / 32000),
                    }
                )
            elif packet.get("text"):
                control = json.loads(packet["text"]).get("type")
                if control == "pause" and state == "running":
                    state = "paused"
                elif control == "resume" and state == "paused":
                    state = "running"
                elif control in ("stop", "finish"):
                    result = await adapter.finalize_segment()
                    await emit_result(result)
                    state = "finished" if control == "finish" else "stopped"
                    await ws.send_json({"type": "ended", "status": state})
                    break
                else:
                    await error("INVALID_STATE")
                    continue
                await ws.send_json({"type": "state", "status": state})
    except ASRError as e:
        state = "failed"
        await error(e.code)
    except (WebSocketDisconnect, RuntimeError):
        state = "disconnected"
    except asyncio.TimeoutError:
        state = "timeout"
        try:
            await error("TIMEOUT")
        except RuntimeError:
            pass
    except Exception:
        state = "failed"
        try:
            await error("SESSION_FAILED")
        except RuntimeError:
            pass
    finally:
        if adapter:
            await adapter.end_session()
            save(
                "session",
                sid,
                {
                    "id": sid,
                    "source_id": source,
                    "status": state,
                    "asr_engine": PROVIDER,
                    "audio_time": samples / 16000,
                    "recognition_mode": recognition_mode,
                    "audio_offset": audio_offset,
                },
            )
        try:
            await ws.close()
        except RuntimeError:
            pass
