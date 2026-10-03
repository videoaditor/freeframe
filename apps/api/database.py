import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Import settings - handle both package and direct execution
try:
    from .config import settings
except ImportError:
    from config import settings

# pool_pre_ping: a transcode holds no connection while ffmpeg runs (commit releases it), so the
# first write after a long encode checks a connection out of the pool - one that a Postgres restart
# in the meantime has killed. Without the ping that write fails ("server closed the connection
# unexpectedly", 2026-10-02 10:18 UTC) and a finished transcode is thrown away.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
