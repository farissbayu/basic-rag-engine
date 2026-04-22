from sqlmodel import SQLModel, Field
from ulid import ULID


def generate_ulid():
    return str(ULID())


class Document(SQLModel, table=True):
    id: str = Field(default_factory=generate_ulid, primary_key=True)
    filename: str
    size: int
    uploaded_at: str
