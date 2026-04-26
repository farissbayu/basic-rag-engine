from sqlmodel import Session
from app.core.engine import engine
from app.utils.chromadb_client import get_pdf_collection
from chromadb import Collection
from openai import OpenAI
from app.utils.openai import oa_client


def get_db_session() -> Session:
    return Session(engine)


def get_collection() -> Collection:
    return get_pdf_collection()


def get_llm_client() -> OpenAI:
    return oa_client
