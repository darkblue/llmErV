FIELDS = ['event_type', 'flight', 'location', 'occurred_at', 'units', 'emergency_level', 'casualties', 'resources', 'instructions', 'status']

def extract(segment):
    text = segment['text']
    fields = {key: {'value': None, 'verification': 'unknown', 'evidence': None} for key in FIELDS}
    # A demo transcript is never treated as emergency evidence.
    if segment['asr_engine'] != 'mock':
        import re
        patterns = {'event_type': r'起火|烟雾|漏油|跑道入侵|人员受伤|紧急撤离', 'flight': r'(?:[A-Z]{2}|国航|南航|东航)\s?\d{3,4}', 'location': r'(?:\d{1,2}[LRC]?跑道|跑道\d{1,2}[LRC]?|[A-Z]\d*滑行道|\d+号机位)', 'units': r'消防|医疗|公安|塔台|机坪', 'emergency_level': r'[一二三123]级应急'}
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                fields[key] = {'value': match.group(), 'verification': 'unverified', 'evidence': {'segment_id': segment['segment_id'], 'text': text, 'start_time': segment['start_time'], 'end_time': segment['end_time']}}
    return {'session_id': segment['session_id'], 'segment_id': segment['segment_id'], 'provider': 'rules', 'fields': fields, 'advisory_only': True}
