from sqlalchemy import create_engine, String, JSON, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
import os
from pathlib import Path

DATA = Path(os.getenv('DATA_DIR', 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
engine = create_engine(os.getenv('DATABASE_URL', f'sqlite:///{DATA}/llmerv.db'))
DB = sessionmaker(engine)

class Base(DeclarativeBase): pass
class Record(Base):
    __tablename__ = 'records'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)

# Business entities use versionable JSON payloads; PostgreSQL supported by SQLAlchemy.
AudioSource = AudioFile = RecognitionSession = TranscriptSegment = EmergencyEvent = EmergencyEntity = HotwordDictionary = SystemConfiguration = Record
Base.metadata.create_all(engine)

def save(kind, id, payload):
    with DB.begin() as db:
        db.merge(Record(id=id, kind=kind, payload=payload))

def get(id):
    with DB() as db:
        row = db.get(Record, id)
        return row.payload if row else None

def listing(kind):
    with DB() as db:
        return [r.payload for r in db.query(Record).filter_by(kind=kind).all()]

def remove(id):
    with DB.begin() as db:
        row = db.get(Record, id)
        if row: db.delete(row)
