from app.core.settings import settings
from sqlmodel import create_engine, Session

engine = create_engine(settings.DATABASE_URL)


def get_db():
    with Session(engine) as session:
        yield session
