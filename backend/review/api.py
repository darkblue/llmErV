import asyncio
import hashlib
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, HttpUrl, model_validator
from backend.models import DATA, save, listing
from backend.events.extract import extract
from .service import (
    document,
    segment,
    propose,
    commit_revision,
    current_text,
    fingerprint,
    validate_pair,
    TERMS,
)

router = APIRouter()
MAX_PDF_BYTES = 15 * 1024 * 1024
REFERENCE_DIR = DATA / "references"
REFERENCE_DIR.mkdir(exist_ok=True)


@router.get("/transcripts/{id}/radio-digits")
def radio_digit_review(id: str):
    from backend.asr.radio_digits import candidate

    item = segment(id)
    value = (
        None
        if item["asr_engine"] == "mock"
        else candidate(
            current_text(item), item.get("recognition_mode") == "radio_digits"
        )
    )
    return {"base_hash": fingerprint(current_text(item)), "candidate": value}


class DigitApproval(BaseModel):
    base_hash: str = Field(min_length=64, max_length=64)
    acknowledge_audio_review: bool = False


@router.post("/transcripts/{id}/radio-digits/apply")
def apply_radio_digits(id: str, body: DigitApproval):
    item = segment(id)
    result = radio_digit_review(id)
    if result["base_hash"] != body.base_hash:
        raise HTTPException(409, "STALE_TRANSCRIPT_REVIEW_AGAIN")
    if not body.acknowledge_audio_review:
        raise HTTPException(422, "AUDIO_REVIEW_ACK_REQUIRED")
    value = result["candidate"]
    if value is None:
        raise HTTPException(422, "NO_RADIO_DIGIT_CANDIDATE")
    evidence = [
        {
            "id": "caac_radio_digits",
            "before": current_text(item),
            "after": value["digits"],
            "references": [],
            "digit_profile": value,
        }
    ]
    return commit_revision(
        id, body.base_hash, value["digits"], "radio_digit_review", evidence
    )


@router.get("/references")
def references():
    return listing("reference")


@router.get("/review/capabilities")
def capabilities():
    return {
        "allowed_terms": sorted(TERMS),
        "engine": "bounded_term_rules",
        "automatic_apply": False,
        "caac_compliance_audit": False,
        "audio_evidence_required": True,
    }


def pdf_text(path):
    info = subprocess.run(
        ["pdfinfo", str(path)], capture_output=True, timeout=15, check=True
    )
    metadata = info.stdout.decode(errors="replace")
    import re

    found = re.search(r"^Pages:\s+(\d+)", metadata, re.M)
    pages = int(found[1]) if found else 0
    if not 0 < pages <= 200:
        raise ValueError("page limit")
    text = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        timeout=20,
        check=True,
    ).stdout.decode("utf-8", errors="replace")
    texts = text.split("\f")[:pages]
    if sum(map(len, texts)) > 500000:
        raise ValueError("text limit")
    return pages, texts


@router.post("/references", status_code=201)
async def upload_reference(
    file: UploadFile,
    kind: Literal["exercise_card", "caac_standard"] = Query(...),
    source_url: HttpUrl | None = Query(default=None),
):
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(415, "PDF_REQUIRED")
    id = str(uuid.uuid4())
    path = REFERENCE_DIR / f"{id}.pdf"
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PDF_BYTES:
                    raise HTTPException(413, "REFERENCE_TOO_LARGE")
                digest.update(chunk)
                out.write(chunk)
        if not path.read_bytes()[:5] == b"%PDF-":
            raise ValueError("header")
        pages, texts = await asyncio.to_thread(pdf_text, path)
        excerpts = [
            {
                "id": str(uuid.uuid4()),
                "page": index + 1,
                "text": text.strip(),
                "verified": False,
                "source_method": "pdf_text_extraction",
            }
            for index, text in enumerate(texts)
            if text.strip()
        ]
        item = {
            "entity": "reference",
            "id": id,
            "title": Path(file.filename).name,
            "kind": kind,
            "sha256": digest.hexdigest(),
            "pages": pages,
            "size": size,
            "source_url": str(source_url) if source_url else None,
            "detected_standard_id": "MH/T 4014-2003"
            if kind == "caac_standard"
            and re.search(r"MH\s*/\s*T\s*4014\s*[—－-]\s*2003", "\n".join(texts))
            else None,
            "extraction_status": "extracted_needs_review"
            if excerpts
            else "scan_needs_manual_transcription",
            "excerpts": excerpts,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        save("reference", id, item)
        return item
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except (ValueError, OSError, subprocess.SubprocessError):
        path.unlink(missing_ok=True)
        raise HTTPException(422, "INVALID_PDF_OR_EXTRACTION_FAILED")
    finally:
        await file.close()


@router.get("/references/{id}/content")
def reference_content(id: str):
    document(id)
    path = REFERENCE_DIR / f"{id}.pdf"
    if not path.is_file():
        raise HTTPException(404, "REFERENCE_FILE_MISSING")
    return FileResponse(path, media_type="application/pdf")


class ExcerptInput(BaseModel):
    page: int = Field(ge=1, le=200)
    text: str = Field(min_length=1, max_length=10000)


@router.post("/references/{id}/excerpts", status_code=201)
def add_excerpt(id: str, body: ExcerptInput):
    ref = document(id)
    if body.page > ref["pages"] or not body.text.strip():
        raise HTTPException(422, "INVALID_EXCERPT_PAGE_OR_TEXT")
    if len(ref["excerpts"]) >= 250:
        raise HTTPException(422, "EXCERPT_LIMIT")
    excerpt = {
        "id": str(uuid.uuid4()),
        "page": body.page,
        "text": body.text.strip(),
        "verified": False,
        "source_method": "manual_transcription",
    }
    ref["excerpts"].append(excerpt)
    save("reference", id, ref)
    return ref


class VerifyInput(BaseModel):
    verified: bool
    acknowledge_source_review: bool = False


@router.put("/references/{id}/excerpts/{excerpt_id}/verification")
def verify_excerpt(id: str, excerpt_id: str, body: VerifyInput):
    ref = document(id)
    excerpt = next((x for x in ref["excerpts"] if x["id"] == excerpt_id), None)
    if excerpt is None:
        raise HTTPException(404, "EXCERPT_NOT_FOUND")
    if body.verified and not body.acknowledge_source_review:
        raise HTTPException(422, "SOURCE_REVIEW_ACK_REQUIRED")
    excerpt["verified"] = body.verified
    excerpt["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    save("reference", id, ref)
    return ref


class RuleInput(BaseModel):
    reference_id: str
    excerpt_id: str
    before: str = Field(min_length=2, max_length=12)
    after: str = Field(min_length=2, max_length=12)


@router.get("/review/rules")
def rules():
    return listing("correction_rule")


@router.post("/review/rules", status_code=201)
def add_rule(body: RuleInput):
    validate_pair(body.before, body.after)
    ref = document(body.reference_id)
    excerpt = next((x for x in ref["excerpts"] if x["id"] == body.excerpt_id), None)
    if not excerpt or body.after not in excerpt["text"]:
        raise HTTPException(422, "RULE_NOT_SUPPORTED_BY_EXCERPT")
    id = str(uuid.uuid4())
    item = {"id": id, **body.model_dump()}
    save("correction_rule", id, item)
    return item


class ReviewInput(BaseModel):
    reference_ids: list[str] = Field(min_length=1, max_length=20)
    communication_context: Literal["aoc_rescue", "atc_air_ground", "unknown"] = (
        "aoc_rescue"
    )


@router.post("/transcripts/{id}/review")
def review(id: str, body: ReviewInput):
    return propose(segment(id), body.reference_ids, body.communication_context)


class ApplyInput(ReviewInput):
    base_hash: str = Field(min_length=64, max_length=64)
    suggestion_ids: list[str] = Field(min_length=1, max_length=100)
    acknowledge_audio_review: bool = False


@router.post("/transcripts/{id}/review/apply")
def apply(id: str, body: ApplyInput):
    item = segment(id)
    result = propose(item, body.reference_ids, body.communication_context)
    if result["base_hash"] != body.base_hash:
        raise HTTPException(409, "STALE_TRANSCRIPT_REVIEW_AGAIN")
    if not body.acknowledge_audio_review:
        raise HTTPException(422, "AUDIO_REVIEW_ACK_REQUIRED")
    available = {s["id"]: s for s in result["suggestions"]}
    choices = []
    for key in set(body.suggestion_ids):
        if key not in available:
            raise HTTPException(422, "INVALID_SUGGESTION")
        choice = available[key]
        if not choice["can_apply"]:
            raise HTTPException(422, "REFERENCE_REVIEW_REQUIRED")
        choices.append(choice)
    ordered = sorted(choices, key=lambda x: x["start"])
    if any(a["end"] > b["start"] for a, b in zip(ordered, ordered[1:])):
        raise HTTPException(422, "OVERLAPPING_SUGGESTIONS")
    text = current_text(item)
    for choice in reversed(ordered):
        text = text[: choice["start"]] + choice["after"] + text[choice["end"] :]
    return commit_revision(id, body.base_hash, text, "reference_term_review", ordered)


@router.get("/transcripts/{id}/revisions")
def revisions(id: str):
    segment(id)
    return sorted(
        [r for r in listing("transcript_revision") if r["segment_id"] == id],
        key=lambda r: r["version"],
    )


class TranscriptInput(BaseModel):
    source_id: str
    text: str = Field(min_length=1, max_length=10000)
    start_time: float = Field(ge=0, allow_inf_nan=False)
    end_time: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def times(self):
        if self.end_time <= self.start_time or not self.text.strip():
            raise ValueError("invalid range or empty text")
        return self


@router.post("/transcripts/import", status_code=201)
def import_transcript(body: TranscriptInput):
    audio = next((x for x in listing("audio") if x["id"] == body.source_id), None)
    if not audio:
        raise HTTPException(404, "AUDIO_NOT_FOUND")
    if body.end_time > audio["duration"] + 0.01:
        raise HTTPException(422, "TRANSCRIPT_OUTSIDE_AUDIO")
    sid, id = str(uuid.uuid4()), str(uuid.uuid4())
    item = {
        "session_id": sid,
        "source_id": body.source_id,
        "segment_id": id,
        "text": body.text,
        "original_text": body.text,
        "corrected_text": body.text,
        "start_time": body.start_time,
        "end_time": body.end_time,
        "is_final": True,
        "confidence": None,
        "speaker_id": None,
        "asr_engine": "manual_input",
        "provenance": "user_supplied_not_asr",
    }
    save(
        "session",
        sid,
        {
            "id": sid,
            "source_id": body.source_id,
            "status": "imported",
            "asr_engine": "manual_input",
            "audio_time": body.end_time - body.start_time,
        },
    )
    save("transcript", id, item)
    save("event", id + ":event", extract(item))
    return item
