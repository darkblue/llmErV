"""Reference-bound, human-approved transcript corrections; no ASR or command generation."""

import copy
import hashlib
import re
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import update
from backend.models import DB, Record, get, listing
from backend.events.extract import extract

# Generic vocabulary only. Operational actions, numbers, names and locations are
# deliberately outside the rule vocabulary. Extending this needs code review.
TERMS = {
    "指挥中心",
    "五方通话",
    "应急救援方格网图",
    "应急救援频道",
    "机坪",
    "塔台",
    "消防救援部",
    "医疗救护",
    "航空器",
    "航班",
    "滑行道",
    "对讲机",
}
CONFUSIONS = {
    "指回中心": "指挥中心",
    "指挥中芯": "指挥中心",
    "五方通化": "五方通话",
    "应急救援频到": "应急救援频道",
    "应急救援方格网途": "应急救援方格网图",
    "机平": "机坪",
    "塔抬": "塔台",
    "消房救援部": "消防救援部",
    "对讲鸡": "对讲机",
}


def fingerprint(text):
    return hashlib.sha256(text.encode()).hexdigest()


def current_text(segment):
    return segment.get("corrected_text", segment["text"])


def document(id):
    value = get(id)
    if not value or value.get("entity") != "reference":
        raise HTTPException(404, "REFERENCE_NOT_FOUND")
    return value


def segment(id):
    value = get(id)
    if not value or not value.get("is_final") or value.get("segment_id") != id:
        raise HTTPException(404, "FINAL_SEGMENT_NOT_FOUND")
    return value


def edit_distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j - 1] + (x != y)))
        row = new
    return row[-1]


def validate_pair(before, after):
    # Exact, small generic term changes. No action/negation/digit/callsign edits.
    if (
        after not in TERMS
        or before == after
        or re.search(r"[\dA-Za-z不无未禁否]", before)
        or edit_distance(before, after) > 1
    ):
        raise HTTPException(422, "UNSAFE_RULE_USE_MANUAL_REVIEW")


def citation(ref, excerpt):
    return {
        "reference_id": ref["id"],
        "title": ref["title"],
        "kind": ref["kind"],
        "file_sha256": ref["sha256"],
        "source_url": ref.get("source_url"),
        "page": excerpt["page"],
        "excerpt_id": excerpt["id"],
        "quote": excerpt["text"],
        "verified": excerpt["verified"],
        "source_method": excerpt["source_method"],
        "interpretation": "reference_vocabulary_only_not_audio_evidence",
    }


def reference_notes(refs, context):
    """Human review checklist, never an automated finding of compliance."""
    notes = []
    clauses = [
        (
            "3.1",
            r"3[.．]1\s+总则",
            "适用范围核对",
            "该标准针对空中交通服务单位与航空器的话音联络；机场 AOC 救援通报不能直接等同为空地管制通话。",
            "all",
        ),
        (
            "3.3",
            r"3[.．]3\s+通话基本要求",
            "表达与发音核对",
            "回听清晰度、语速、数字前停顿及信息完整性；不能仅凭转写文本认定发音合规。",
            "all",
        ),
        (
            "3.2",
            r"3[.．]2\s+通话结构",
            "呼号结构核对",
            "首次联系核对对方呼号、己方呼号、通话内容；不据此补写未听到的呼号。",
            "atc_air_ground",
        ),
        (
            "3.4.1",
            r"3[.．]4[.．]1\s+数字的读法",
            "数字读法核对",
            "应逐项结合具体场景回听数字读法；不自动转换航班号、跑道或数值。",
            "atc_air_ground",
        ),
        (
            "3.9",
            r"3[.．]9\s+许可的发布和复诵要求",
            "许可与复诵核对",
            "人工核对涉及安全的许可、指示和复诵；没有对话双方及原音频不能认定漏报或复诵正确。",
            "atc_air_ground",
        ),
    ]
    markers = {
        "3.1": "空中交通服务单位与航空器",
        "3.2": "首次联系",
        "3.3": "先想后说",
        "3.4.1": "数字的汉语",
        "3.9": "缓慢、清楚",
    }
    for ref in refs:
        if ref.get("detected_standard_id") != "MH/T 4014-2003":
            continue
        for clause, pattern, title, note, scope in clauses:
            if scope != "all" and context != scope:
                continue
            for excerpt in ref["excerpts"]:
                if (
                    re.search(pattern, excerpt["text"])
                    and markers[clause] in excerpt["text"]
                ):
                    notes.append(
                        {
                            "clause": clause,
                            "title": title,
                            "note": note,
                            "context": context,
                            "status": "human_check_required",
                            "reference": citation(ref, excerpt),
                            "currency": "supplied_2003_edition_current_validity_not_verified",
                        }
                    )
                    break
    return notes


def propose(item, reference_ids, context="aoc_rescue"):
    text = current_text(item)
    base_hash = fingerprint(text)
    if item["asr_engine"] == "mock":
        return {
            "status": "mock_not_reviewable",
            "base_hash": base_hash,
            "suggestions": [],
            "warnings": ["模拟识别不是实际对话，不能用单卡生成转写。"],
        }
    suggestions = []
    allowed_refs = [document(id) for id in reference_ids]
    custom = listing("correction_rule")
    candidates = list(CONFUSIONS.items())
    candidates.extend(
        (r["before"], r["after"]) for r in custom if r["reference_id"] in reference_ids
    )
    seen = set()
    for before, after in candidates:
        # Custom rules are validated again when used, never blindly trusted.
        validate_pair(before, after)
        for match in re.finditer(re.escape(before), text):
            span = (match.start(), match.end(), after)
            if span in seen:
                continue
            refs = []
            for ref in allowed_refs:
                for excerpt in ref["excerpts"]:
                    if after in excerpt["text"]:
                        # Custom pairs must be bound to the selected excerpt.
                        is_default = CONFUSIONS.get(before) == after
                        if is_default or any(
                            r["before"] == before
                            and r["after"] == after
                            and r["reference_id"] == ref["id"]
                            and r["excerpt_id"] == excerpt["id"]
                            for r in custom
                        ):
                            refs.append(citation(ref, excerpt))
            if not refs:
                continue
            seen.add(span)
            id = fingerprint(
                f"{base_hash}:{match.start()}:{match.end()}:{before}:{after}"
            )[:24]
            suggestions.append(
                {
                    "id": id,
                    "start": match.start(),
                    "end": match.end(),
                    "before": before,
                    "after": after,
                    "kind": "terminology_candidate",
                    "reason": "疑似术语错字；仅参考已选资料用词，必须回听确认。",
                    "references": refs,
                    "requires_audio_review": True,
                    "can_apply": any(r["verified"] for r in refs),
                }
            )
    return {
        "status": "review_required",
        "base_hash": base_hash,
        "suggestions": sorted(suggestions, key=lambda x: x["start"]),
        "communication_context": context,
        "reference_notes": reference_notes(allowed_refs, context),
        "warnings": [
            "单卡是演练参考，不证明录音实际说过什么。",
            "不补全或改写呼号、航班号、跑道、方格网、人数、时间、否定词和调度指令。",
            "手写信息、漏报及复诵问题请回听并人工判断；当前不是完整规范合规审查。",
        ],
    }


def commit_revision(id, expected_hash, text, method, evidence=None):
    with DB.begin() as db:
        row = db.get(Record, id)
        if not row or row.kind != "transcript":
            raise HTTPException(404, "FINAL_SEGMENT_NOT_FOUND")
        old = copy.deepcopy(row.payload)
        if fingerprint(current_text(old)) != expected_hash:
            raise HTTPException(409, "STALE_TRANSCRIPT_REVIEW_AGAIN")
        payload = copy.deepcopy(old)
        payload.update(
            corrected_text=text,
            human_edited=True,
            review_version=old.get("review_version", 0) + 1,
        )
        # Compare-and-swap prevents stale reviews replacing concurrent edits.
        updated = db.execute(
            update(Record)
            .where(
                Record.id == id,
                Record.payload["corrected_text"].as_string()
                == old.get("corrected_text"),
                Record.payload["review_version"].as_integer()
                == old.get("review_version"),
            )
            .values(payload=payload),
            execution_options={"synchronize_session": False},
        )
        if updated.rowcount != 1:
            raise HTTPException(409, "STALE_TRANSCRIPT_REVIEW_AGAIN")
        # Transcript, derived event and audit are committed together.
        db.merge(Record(id=id + ":event", kind="event", payload=extract(payload)))
        audit_id = str(uuid.uuid4())
        db.add(
            Record(
                id=audit_id,
                kind="transcript_revision",
                payload={
                    "id": audit_id,
                    "segment_id": id,
                    "session_id": old["session_id"],
                    "source_id": old["source_id"],
                    "start_time": old["start_time"],
                    "end_time": old["end_time"],
                    "before": current_text(old),
                    "after": text,
                    "method": method,
                    "evidence": evidence or [],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "version": payload["review_version"],
                    "actor": "local_operator_unverified_identity",
                    "event_reanalysis": "completed",
                },
            )
        )
        return payload
