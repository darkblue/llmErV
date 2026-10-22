from fastapi.testclient import TestClient
from backend.main import app
from backend.models import get, save
from backend.events.extract import extract
from backend.review.service import commit_revision, fingerprint
from fastapi import HTTPException
import pytest
from pathlib import Path

client = TestClient(app)


def imported(text):
    with (Path(__file__).parent / "fixtures/tone.wav").open("rb") as file:
        audio = client.post("/audio", files={"file": ("events.wav", file)}).json()
    r = client.post(
        "/transcripts/import",
        json={
            "source_id": audio["id"],
            "text": text,
            "start_time": 0,
            "end_time": 2,
        },
    )
    assert r.status_code == 201
    return r.json()


def test_revision_reanalyzes_atomically_preserving_original_and_evidence():
    original = "CA1234，27号跑道起火，请消防前往集结。"
    item = imported(original)
    event_id = item["segment_id"] + ":event"
    assert get(event_id)["fields"]["location"]["value"] == "27号跑道"
    edited = "CA1234，28号跑道未发现起火，请医疗前往集结。"
    r = client.patch("/transcripts/" + item["segment_id"], json={"text": edited})
    assert r.status_code == 200
    assert r.json()["original_text"] == r.json()["text"] == original
    event = get(event_id)
    assert event["fields"]["event_type"]["value"] is None
    assert event["fields"]["location"]["value"] == "28号跑道"
    assert event["fields"]["units"]["value"] == "医疗"
    evidence = event["fields"]["location"]["evidence"]
    assert evidence["text"] == edited and evidence["review_version"] == 1
    assert evidence["text_basis"] == "corrected_text"
    assert event["fields"]["location"]["verification"] == "unverified"
    audit = client.get(f"/transcripts/{item['segment_id']}/revisions").json()
    assert audit[0]["event_reanalysis"] == "completed"
    with pytest.raises(HTTPException) as conflict:
        commit_revision(
            item["segment_id"], fingerprint(original), "过期稿", "manual_edit"
        )
    assert conflict.value.status_code == 409
    assert get(event_id) == event  # Rejected edits cannot corrupt derived analysis.


def test_event_read_repairs_legacy_results_isolates_sessions_and_retracts_empty_edit():
    first = imported("27号跑道起火")
    other = imported("28号跑道烟雾")
    save("event", first["segment_id"] + ":event", {"obsolete": True})
    result = client.get("/events", params={"session_id": first["session_id"]}).json()
    assert len(result) == 1 and result[0]["segment_id"] == first["segment_id"]
    assert result[0]["fields"]["event_type"]["value"] == "起火"
    assert result[0]["segment_id"] != other["segment_id"]
    assert client.get("/events?session_id=nonexistent").json() == []
    assert (
        client.patch(
            "/transcripts/" + first["segment_id"], json={"text": ""}
        ).status_code
        == 200
    )
    result = client.get("/events", params={"session_id": first["session_id"]}).json()
    assert all(f["value"] is None for f in result[0]["fields"].values())


def test_explicit_fields_are_literal_and_missing_information_stays_unknown():
    item = imported(
        "14点30分，CA1234，二七号跑道有烟雾，消防、医疗到场，三级应急，2人受伤，2辆消防车，请立即撤离，正在救援。"
    )
    fields = extract(item)["fields"]
    expected = {
        "occurred_at": "14点30分",
        "flight": "CA1234",
        "location": "二七号跑道",
        "event_type": "烟雾",
        "units": "消防、医疗",
        "emergency_level": "三级应急",
        "casualties": "2人受伤",
        "resources": "2辆消防车",
        "instructions": "请立即撤离",
        "status": "正在救援",
    }
    assert {k: f["value"] for k, f in fields.items()} == expected
    assert all(
        f["evidence"]["segment_id"] == item["segment_id"] for f in fields.values()
    )
    item["corrected_text"] = "欢迎大家来体验语音识别模型"
    assert all(f["value"] is None for f in extract(item)["fields"].values())


@pytest.mark.parametrize(
    "text", ["未发现起火", "没有发现明显烟雾", "无明显漏油", "起火已排除"]
)
def test_denied_hazards_are_not_positive_incident_findings(text):
    item = {
        "text": text,
        "asr_engine": "vosk",
        "session_id": "negation",
        "segment_id": "n",
        "start_time": 0,
        "end_time": 1,
    }
    assert extract(item)["fields"]["event_type"]["value"] is None
    item["asr_engine"] = "mock"
    item["corrected_text"] = "27号跑道起火"
    assert extract(item)["mock_excluded"]
    assert all(f["value"] is None for f in extract(item)["fields"].values())
