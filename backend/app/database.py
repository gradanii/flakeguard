from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def create_database_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def create_session_factory(engine=None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or create_database_engine(), expire_on_commit=False)
