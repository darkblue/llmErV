import json
import subprocess
from pathlib import Path

MAX_DURATION = 1800

def decode(path: Path, target: Path):
    info = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_format', '-show_streams', '-of', 'json', str(path)], capture_output=True, timeout=15, check=True)
    metadata = json.loads(info.stdout)
    stream = next(s for s in metadata['streams'] if s['codec_type'] == 'audio')
    duration = float(metadata['format'].get('duration', stream.get('duration', 0)))
    if not 0 < duration <= MAX_DURATION:
        raise ValueError('音频时长必须在 0–1800 秒之间')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', '0:a:0', '-t', str(MAX_DURATION + 1), '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', '-y', str(target)], capture_output=True, timeout=90, check=True)
    if target.stat().st_size > MAX_DURATION * 32000 + 4096:
        raise ValueError('解码后音频过长')
    return dict(duration=duration, sample_rate=int(stream['sample_rate']), channels=int(stream['channels']), codec=stream['codec_name'])
