"""Original synthetic tone fixture, no human or operational recordings."""
import math
import struct
import wave
from pathlib import Path
path = Path(__file__).resolve().parents[1] / 'tests/fixtures/tone.wav'
path.parent.mkdir(exist_ok=True)
with wave.open(str(path), 'wb') as f:
    f.setnchannels(2)
    f.setsampwidth(2)
    f.setframerate(44100)
    f.writeframes(b''.join(struct.pack('<hh', int(6000*math.sin(2*math.pi*440*i/44100)), int(6000*math.sin(2*math.pi*440*i/44100))) for i in range(44100*4)))
print(path)
