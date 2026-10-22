import re

FIELDS = [
    "event_type",
    "flight",
    "location",
    "occurred_at",
    "units",
    "emergency_level",
    "casualties",
    "resources",
    "instructions",
    "status",
]


def denied(text, match):
    return re.search(
        r"(?:未|没有|无|并未|不是|排除)(?:发现|发生|见)?(?:明显|任何)?\s*$",
        text[max(0, match.start() - 8) : match.start()],
    ) or re.match(r"(?:已)?(?:排除|否认)", text[match.end() : match.end() + 6])


def extract(segment):
    text = segment.get("corrected_text", segment["text"])
    fields = {
        key: {"value": None, "verification": "unknown", "evidence": None}
        for key in FIELDS
    }
    # A demo transcript is never treated as emergency evidence.
    if segment["asr_engine"] != "mock":
        patterns = {
            "event_type": r"起火|烟雾|漏油|跑道入侵|人员受伤|紧急撤离",
            "flight": r"(?:[A-Z]{2}|国航|南航|东航)\s?\d{3,4}",
            "location": r"(?:[\d零一二三四五六七八九两幺洞]{1,3}[LRC]?(?:号)?跑道|跑道\s?\d{1,2}[LRC]?|[A-Z]\d*(?:号)?滑行道|\d+号机位|\d+号集结点)",
            "units": r"消防(?!车)|医疗|公安|塔台|机坪",
            "emergency_level": r"[一二三123]级应急",
            "occurred_at": r"(?:\d{1,2}:\d{2}|[\d零一二三四五六七八九十两]{1,3}[时点](?:[\d零一二三四五六七八九十]{1,3}分)?)",
            "casualties": r"(?:无人(?:伤亡|受伤)|无人员伤亡|[\d一二三四五六七八九十两]+(?:名|人)(?:人员)?(?:受伤|死亡|失踪)|人员受伤)",
            "resources": r"(?:(?:\d+|[一二三四五六七八九十两]+)(?:辆|台))?(?:消防车|救护车|救援车辆|担架|灭火器)",
            "instructions": r"[^，。！？；\n]*(?:禁止进入|不要进入|不得进入|停止作业|停止运行|立即撤离|前往|请求支援|请求增援|请.*集结)[^，。！？；\n]*",
            "status": r"明火已扑灭|火已扑灭|已扑灭|救援结束|处置完成|正在救援|正在处置|已解除警报",
        }
        for key, pattern in patterns.items():
            matches = list(re.finditer(pattern, text))
            if key in {"event_type", "casualties", "status"}:
                # A denied hazard must not become a positive incident finding.
                matches = [m for m in matches if not denied(text, m)]
            if key == "resources":
                needs = []
                for match in matches:
                    prefix = re.split(r"[，。！？；\n]", text[: match.start()])[-1][
                        -80:
                    ]
                    if re.search(
                        r"需|请|申请|增派|调派|派出|支援", prefix
                    ) and not re.search(r"不需要|无需|不必|不需|不要", prefix):
                        needs.append(match)
                matches = needs
            if matches:
                fields[key] = {
                    "value": "、".join(
                        dict.fromkeys(m.group().strip() for m in matches)
                    ),
                    "verification": "unverified",
                    "evidence": {
                        "segment_id": segment["segment_id"],
                        "text": text,
                        "start_time": segment["start_time"],
                        "end_time": segment["end_time"],
                        "review_version": segment.get("review_version", 0),
                        "text_basis": "corrected_text"
                        if segment.get("human_edited")
                        else "transcript",
                    },
                }
    return {
        "session_id": segment["session_id"],
        "segment_id": segment["segment_id"],
        "provider": "rules",
        "review_version": segment.get("review_version", 0),
        "mock_excluded": segment["asr_engine"] == "mock",
        "fields": fields,
        "advisory_only": True,
    }
